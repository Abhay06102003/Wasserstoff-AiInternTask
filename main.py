import os
import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from PyPDF2 import PdfReader
from pymongo import MongoClient, UpdateOne
import spacy
from collections import Counter
from datetime import datetime
import psutil
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv
import os
load_dotenv()

@dataclass
class ProcessingConfig:
    """Configuration for document processing based on document size"""
    SHORT_DOC_THRESHOLD: int = 10  # pages
    MEDIUM_DOC_THRESHOLD: int = 50  # pages
    SHORT_SUMMARY_RATIO: float = 0.25
    MEDIUM_SUMMARY_RATIO: float = 0.2
    LONG_SUMMARY_RATIO: float = 0.15
    MIN_KEYWORD_FREQ: int = 3
    MAX_KEYWORDS = {"small" : 25,"medium":75,"large":100}
    BATCH_SIZE: int = 10


class DocumentProcessor:
    """Base class for document processing operations"""
    def __init__(self):
        self.nlp = spacy.load('en_core_web_sm')
        self.config = ProcessingConfig()

    def get_summary_ratio(self, page_count: int) -> float:
        """Determine summary ratio based on document length"""
        if page_count <= self.config.SHORT_DOC_THRESHOLD:
            return self.config.SHORT_SUMMARY_RATIO
        elif page_count <= self.config.MEDIUM_DOC_THRESHOLD:
            return self.config.MEDIUM_SUMMARY_RATIO
        return self.config.LONG_SUMMARY_RATIO

    def generate_summary(self, text: str, page_count: int) -> str:
        """Generate dynamic summary based on document length"""
        try:
            doc = self.nlp(text)
            sentences = list(doc.sents)
            
            # Calculate summary length based on document size
            ratio = self.get_summary_ratio(page_count)
            summary_length = max(3, int(len(sentences) * ratio))
            
            # Calculate sentence importance scores
            sentence_scores = {}
            for sent in sentences:
                words = [token.text.lower() for token in sent if not token.is_stop]
                if words:
                    # Enhanced scoring considering sentence position and length
                    position_score = 1.0 - (sentences.index(sent) / len(sentences))
                    length_score = min(1.0, len(words) / 20)  # Normalize long sentences
                    word_importance = sum(len(word) for word in words) / len(words)
                    sentence_scores[sent] = (position_score + length_score + word_importance) / 3
            
            # Select and order top sentences
            top_sentences = sorted(sentence_scores.items(), 
                                 key=lambda x: x[1], 
                                 reverse=True)[:summary_length]
            
            summary = ' '.join([str(sent[0]) for sent in sorted(top_sentences, 
                              key=lambda x: sentences.index(x[0]))])
            return summary
        except Exception as e:
            logging.error(f"Summary generation error: {str(e)}")
            raise

    def extract_keywords(self, text: str,page_count) -> List[str]:
        """Extract domain-specific keywords with enhanced filtering"""
        try:
            doc = self.nlp(text)
            keywords = []
            
            # Extract noun phrases and named entities
            for chunk in doc.noun_chunks:
                if not any(token.is_stop for token in chunk):
                    keywords.append(chunk.text.lower())
            
            for ent in doc.ents:
                if ent.label_ in ['ORG', 'PRODUCT', 'WORK_OF_ART', 'EVENT', 'LAW']:
                    keywords.append(ent.text.lower())
            
            # Count and filter keywords
            keyword_freq = Counter(keywords)
            
            # Get max keywords based on page count
            if page_count < 10:
                max_keywords = self.config.MAX_KEYWORDS['small']
            elif 10 <= page_count <= 50:
                max_keywords = self.config.MAX_KEYWORDS['medium']
            else:
                max_keywords = self.config.MAX_KEYWORDS['large']
            
            # Enhanced filtering criteria
            filtered_keywords = [
                word for word, freq in keyword_freq.most_common(max_keywords)
                if len(word) > 3 
                and freq >= self.config.MIN_KEYWORD_FREQ
                and not any(char.isdigit() for char in word)
            ]
            
            return filtered_keywords[:max_keywords]
        except Exception as e:
            logging.error(f"Keyword extraction error: {str(e)}")
            raise

class MongoDBHandler:
    """Handle all MongoDB operations"""
    def __init__(self, uri: str, db_name: str, collection_name: str):
        self.client = MongoClient(
            uri,
            serverSelectionTimeoutMS=30000,
            connectTimeoutMS=30000,
            socketTimeoutMS=30000,
            retryWrites=True,
            retryReads=True,
            w='majority',
            maxPoolSize=50,
            waitQueueTimeoutMS=30000
        )
        self.db = self.client[db_name]
        self.collection = self.db[collection_name]
        self.lock = threading.Lock()
        self._test_connection()

    def _test_connection(self):
        """Test MongoDB connection"""
        try:
            self.client.admin.command('ping')
        except (ConnectionFailure, ServerSelectionTimeoutError) as e:
            logging.error(f"MongoDB connection failed: {str(e)}")
            raise

    def store_document(self, metadata: Dict) -> str:
        """Store initial document record"""
        with self.lock:
            try:
                result = self.collection.insert_one(metadata)
                return result.inserted_id
            except Exception as e:
                logging.error(f"MongoDB storage error: {str(e)}")
                raise

    def update_document(self, doc_id: str, update_data: Dict) -> None:
        """Update document record with processing results"""
        with self.lock:
            try:
                self.collection.update_one(
                    {"_id": doc_id},
                    {"$set": update_data}
                )
            except Exception as e:
                logging.error(f"MongoDB update error: {str(e)}")
                raise

    def batch_update(self, updates: List[UpdateOne]) -> None:
        """Perform batch updates to MongoDB"""
        with self.lock:
            try:
                if updates:
                    self.collection.bulk_write(updates, ordered=False)
            except Exception as e:
                logging.error(f"MongoDB batch update error: {str(e)}")
                raise


class PDFProcessor:
    """Main PDF processing pipeline"""
    def __init__(self, mongodb_uri: str, db_name: str, collection_name: str):
        self.doc_processor = DocumentProcessor()
        self.db_handler = MongoDBHandler(mongodb_uri, db_name, collection_name)
        self.config = ProcessingConfig()

    @staticmethod
    def monitor_performance(func):
        """Decorator for performance monitoring"""
        def wrapper(*args, **kwargs):
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss
            
            result = func(*args, **kwargs)
            
            end_time = time.time()
            end_memory = psutil.Process().memory_info().rss
            
            metrics = {
                "function": func.__name__,
                "execution_time": f"{end_time - start_time:.2f}s",
                "memory_usage": f"{(end_memory - start_memory) / 1024 / 1024:.2f}MB"
            }
            
            logging.info(f"Performance Metrics: {json.dumps(metrics, indent=2)}")
            return result
        return wrapper

    def _extract_text_and_metadata(self, file_path: str) -> Tuple[str, Dict]:
        """Extract text and metadata from PDF"""
        try:
            with open(file_path, 'rb') as file:
                reader = PdfReader(file)
                text = ""
                for page in reader.pages:
                    text += page.extract_text() + "\n"
                
                metadata = {
                    "filename": os.path.basename(file_path),
                    "file_path": file_path,
                    "file_size": os.path.getsize(file_path),
                    "page_count": len(reader.pages),
                    "creation_date": datetime.now().isoformat(),
                    "processing_status": "pending"
                }
                
                return text, metadata
        except Exception as e:
            logging.error(f"PDF extraction error for {file_path}: {str(e)}")
            raise

    @monitor_performance
    def process_single_pdf(self, file_path: str) -> Dict:
        """Process a single PDF file"""
        try:
            # Extract text and metadata
            text, metadata = self._extract_text_and_metadata(file_path)
            
            # Store initial record
            doc_id = self.db_handler.store_document(metadata)
            
            # Process content
            summary = self.doc_processor.generate_summary(text, metadata['page_count'])
            keywords = self.doc_processor.extract_keywords(text,metadata['page_count'])
            
            # Update record
            update_data = {
                "summary": summary,
                "keywords": keywords,
                "processing_status": "completed",
                "last_updated": datetime.now().isoformat()
            }
            self.db_handler.update_document(doc_id, update_data)
            
            return {
                "status": "success",
                "file": file_path,
                "doc_id": str(doc_id),
                "summary_length": len(summary),
                "keyword_count": len(keywords)
            }
        except Exception as e:
            logging.error(f"Processing error for {file_path}: {str(e)}")
            return {"status": "error", "file": file_path, "error": str(e)}

    @monitor_performance
    def process_folder(self, folder_path: str, max_workers: int = 10) -> List[Dict]:
        """Process all PDFs in the specified folder concurrently"""
        pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []
            for pdf_file in pdf_files:
                file_path = os.path.join(folder_path, pdf_file)
                futures.append(executor.submit(self.process_single_pdf, file_path))
            
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    logging.info(f"Processed document: {result}")
                except Exception as e:
                    logging.error(f"Error in future: {str(e)}")
        
        return results


if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('pdf_pipeline.log'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize processor
    processor = PDFProcessor(
        mongodb_uri=os.getenv("uri"),
        db_name="Proj",
        collection_name="Proj2"
    )
    
    # Process folder
    results = processor.process_folder("pdfs", max_workers=4)
    
    # Log summary
    success_count = sum(1 for r in results if r['status'] == 'success')
    error_count = sum(1 for r in results if r['status'] == 'error')
    logging.info(f"""
    Processing Summary:
    - Total documents: {len(results)}
    - Successful: {success_count}
    - Failed: {error_count}
    """)