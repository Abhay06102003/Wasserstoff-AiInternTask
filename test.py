import unittest
import os
import time
import json
import logging
from typing import Dict, List, Union
import pandas as pd
import matplotlib.pyplot as plt
from unittest.mock import Mock, patch
import numpy as np
import psutil
from pymongo import MongoClient
from bson import ObjectId
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from main import PDFProcessor, DocumentProcessor, MongoDBHandler, ProcessingConfig

class TestPDFPipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment with existing PDFs"""
        # Configure logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filename='pipeline_test_results.log'
        )
        
        # Define paths to your existing PDFs
        cls.test_dir = "test_data"  
        cls.test_files = [
            os.path.join(cls.test_dir, "small.pdf"),
            os.path.join(cls.test_dir, "medium.pdf"),
            os.path.join(cls.test_dir, "large.pdf")
        ]
        # Ensure MAX_KEYWORDS is a dictionary and handle dynamic keywords based on file size
        cls.max_keywords = {"small": 25, "medium": 75, "large": 100}

        
        # Verify test files exist
        for file_path in cls.test_files:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Test file not found: {file_path}")
        
        try:
            # Initialize processor with test database
            cls.processor = PDFProcessor(
                mongodb_uri=os.getenv("uri"),
                db_name="Proj",
                collection_name="test"
            )
            
        except Exception as e:
            logging.error(f"Failed to initialize PDFProcessor: {str(e)}")
            raise
        
        # Performance metrics storage
        cls.performance_metrics = []
        
        # Store initial file information
        cls.file_info = {}
        for file_path in cls.test_files:
            try:
                cls.file_info[file_path] = {
                    'size': os.path.getsize(file_path),
                    'name': os.path.basename(file_path)
                }
            except OSError as e:
                logging.error(f"Failed to get file info for {file_path}: {str(e)}")
                raise
    @classmethod
    def _get_file_size_type(cls, pages):
        """Helper to determine file size type for dynamic MAX_KEYWORDS."""
        # size_in_mb = file_size / (1024 * 1024)
        if pages < 10:
            return "small"
        elif pages >= 10 and pages < 50:
            return "medium"
        else:
            return "large"

    def setUp(self):
        """Reset database before each test"""
        try:
            self.processor.db_handler.collection.drop()
        except Exception as e:
            logging.error(f"Failed to drop collection: {str(e)}")
            raise

    def _verify_document_structure(self, doc: Dict) -> None:
        """Verify the structure and content of processed document"""
        try:
            file_size_type = self._get_file_size_type(doc['page_count'])
            max_keywords_for_file = self.max_keywords.get(file_size_type, 20)
            # Basic structure checks
            self.assertIsNotNone(doc, "Document is None")
            self.assertIn('summary', doc, "Summary field missing")
            self.assertIn('keywords', doc, "Keywords field missing")
            self.assertIn('processing_status', doc, "Processing status missing")
            
            # Type checks
            self.assertIsInstance(doc['summary'], str, "Summary is not a string")
            self.assertIsInstance(doc['keywords'], list, "Keywords is not a list")
            self.assertIsInstance(doc['processing_status'], str, "Processing status is not a string")
            
            # Content checks
            self.assertTrue(len(doc['summary']) > 0, "Summary is empty")
            self.assertTrue(isinstance(doc['keywords'], list) and len(doc['keywords']) > 0, 
                          "No keywords extracted")
            
            # Use the class-level max_keywords value that was properly converted during setup
            self.assertTrue(len(doc['keywords']) <= max_keywords_for_file,
                f"Too many keywords extracted: {len(doc['keywords'])} > {max_keywords_for_file}")
            
        except AssertionError as e:
            logging.error(f"Document structure verification failed: {str(e)}")
            raise

    def _analyze_content_quality(self, doc: Dict) -> Dict:
        """Analyze the quality of processed content"""
        try:
            summary = str(doc.get('summary', ''))
            keywords = list(doc.get('keywords', []))
            
            # Safely calculate metrics with error handling
            sentences = summary.split('. ')
            words = summary.split()
            
            metrics = {
                'avg_sentence_length': (len(words) / len(sentences)) if sentences else 0,
                'keyword_diversity': (len(set(keywords)) / len(keywords)) if keywords else 0,
                'summary_to_keyword_ratio': (len(summary) / len(' '.join(keywords))) if keywords else 0
            }
            
            return metrics
            
        except Exception as e:
            logging.error(f"Content quality analysis failed: {str(e)}")
            return {
                'avg_sentence_length': 0,
                'keyword_diversity': 0,
                'summary_to_keyword_ratio': 0
            }

    def test_processing_accuracy(self):
        """Test accuracy of document processing"""
        for file_path in self.test_files:
            try:
                # Record start time and memory
                start_time = time.time()
                start_memory = psutil.Process().memory_info().rss
                
                # Process PDF
                result = self.processor.process_single_pdf(file_path)
                
                # Record end time and memory
                processing_time = time.time() - start_time
                memory_used = psutil.Process().memory_info().rss - start_memory
                
                # Verify basic processing success
                self.assertEqual(result['status'], 'success', 
                               f"Processing failed for {os.path.basename(file_path)}")
                
                # Safely convert document ID and retrieve document
                doc_id = result.get('doc_id')
                if isinstance(doc_id, str):
                    doc_id = ObjectId(doc_id)
                
                doc = self.processor.db_handler.collection.find_one({"_id": doc_id})
                self.assertIsNotNone(doc, f"Document not found for ID: {doc_id}")
                
                # Document structure verification
                self._verify_document_structure(doc)
                
                # Content quality verification
                quality_metrics = self._analyze_content_quality(doc)
                
                # Store comprehensive metrics
                self.performance_metrics.append({
                    'filename': os.path.basename(file_path),
                    'file_size': self.file_info[file_path]['size'],
                    'processing_time': float(processing_time),
                    'memory_used': int(memory_used),
                    'summary_length': len(str(doc.get('summary', ''))),
                    'keyword_count': len(list(doc.get('keywords', []))),
                    'quality_metrics': quality_metrics,
                    'timestamp': datetime.now().isoformat()
                })
                
                # Log individual file results
                logging.info(f"""
                File Processing Results - {os.path.basename(file_path)}:
                - Processing Time: {processing_time:.2f} seconds
                - Memory Used: {memory_used / (1024 * 1024):.2f} MB
                - Summary Length: {len(str(doc.get('summary', '')))} characters
                - Keywords Found: {len(list(doc.get('keywords', [])))}
                """)
                
            except Exception as e:
                logging.error(f"Error processing file {file_path}: {str(e)}")
                raise

    def test_concurrent_processing(self):
        """Test concurrent processing performance"""
        try:
            # Record start state
            start_time = time.time()
            start_memory = psutil.Process().memory_info().rss
            
            # Process files concurrently
            results = self.processor.process_folder(self.test_dir, max_workers=4)
            
            # Calculate metrics
            total_time = time.time() - start_time
            total_memory = psutil.Process().memory_info().rss - start_memory
            
            # Verify results
            self.assertEqual(len(results), len(self.test_files))
            success_count = sum(1 for r in results if r.get('status') == 'success')
            self.assertEqual(success_count, len(self.test_files))
            
            # Store concurrent processing metrics
            self.performance_metrics.append({
                'concurrent_processing': {
                    'total_time': float(total_time),
                    'avg_time_per_doc': float(total_time / len(results)),
                    'total_memory_mb': float(total_memory / (1024 * 1024)),
                    'documents_processed': int(len(results)),
                    'timestamp': datetime.now().isoformat()
                }
            })
            
        except Exception as e:
            logging.error(f"Concurrent processing test failed: {str(e)}")
            raise

    @classmethod
    def _create_visualizations(cls, metrics: List[Dict]):
        """Create performance visualization plots"""
        try:
            # Processing time vs file size
            plt.figure(figsize=(10, 6))
            sizes = [float(m['file_size']) / (1024 * 1024) for m in metrics if 'file_size' in m]
            times = [float(m['processing_time']) for m in metrics if 'processing_time' in m]
            
            if sizes and times:
                plt.scatter(sizes, times)
                plt.xlabel('File Size (MB)')
                plt.ylabel('Processing Time (seconds)')
                plt.title('Processing Time vs File Size')
                plt.savefig('time_vs_size.png')
            plt.close()
            
            # Memory usage comparison
            plt.figure(figsize=(10, 6))
            names = [str(m['filename']) for m in metrics if 'filename' in m]
            memory = [float(m['memory_used']) / (1024 * 1024) for m in metrics if 'memory_used' in m]
            
            if names and memory:
                plt.bar(names, memory)
                plt.xlabel('Files')
                plt.ylabel('Memory Usage (MB)')
                plt.title('Memory Usage by File')
                plt.xticks(rotation=45)
                plt.tight_layout()
                plt.savefig('memory_usage.png')
            plt.close()
            
            # Content quality metrics
            if all('quality_metrics' in m for m in metrics):
                plt.figure(figsize=(10, 6))
                quality_metrics = pd.DataFrame(
                    [m['quality_metrics'] for m in metrics],
                    index=[m['filename'] for m in metrics]
                )
                quality_metrics.plot(kind='bar', figsize=(10, 6))
                plt.xlabel('Files')
                plt.ylabel('Metric Value')
                plt.title('Content Quality Metrics by File')
                plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                plt.tight_layout()
                plt.savefig('quality_metrics.png')
                plt.close()
                
        except Exception as e:
            logging.error(f"Failed to create visualizations: {str(e)}")

    @classmethod
    def _generate_performance_report(cls):
        """Generate detailed performance report with visualizations"""
        try:
            # Calculate aggregate metrics
            sequential_metrics = [m for m in cls.performance_metrics if 'filename' in m]
            concurrent_metrics = [m for m in cls.performance_metrics if 'concurrent_processing' in m]
            
            if sequential_metrics:
                report_data = {
                    'timestamp': datetime.now().isoformat(),
                    'summary': {
                        'total_files_processed': len(cls.test_files),
                        'sequential_processing': {
                            'avg_time': float(np.mean([m['processing_time'] for m in sequential_metrics])),
                            'avg_memory': float(np.mean([m['memory_used'] for m in sequential_metrics])),
                            'min_time': float(np.min([m['processing_time'] for m in sequential_metrics])),
                            'max_time': float(np.max([m['processing_time'] for m in sequential_metrics]))
                        },
                        'concurrent_processing': concurrent_metrics[0]['concurrent_processing']
                        if concurrent_metrics else {},
                        'file_specific_metrics': sequential_metrics
                    }
                }
                
                # Save detailed report
                with open('performance_report.json', 'w') as f:
                    json.dump(report_data, f, indent=2)
                
                # Create visualizations
                cls._create_visualizations(sequential_metrics)
                
                # Generate summary log
                logging.info(f"""
                Performance Test Summary:
                - Total files processed: {len(cls.test_files)}
                - Average processing time: {report_data['summary']['sequential_processing']['avg_time']:.2f} seconds
                - Average memory usage: {report_data['summary']['sequential_processing']['avg_memory'] / (1024 * 1024):.2f} MB
                - Concurrent processing time: {report_data['summary']['concurrent_processing'].get('total_time', 'N/A')} seconds
                """)
                
        except Exception as e:
            logging.error(f"Failed to generate performance report: {str(e)}")

    @classmethod
    def tearDownClass(cls):
        """Generate comprehensive performance report"""
        try:
            cls._generate_performance_report()
        except Exception as e:
            logging.error(f"Failed in tearDownClass: {str(e)}")

if __name__ == '__main__':
    unittest.main(verbosity=2)
    print("_______________________________________________________ALL DONE TEST CASES PASSED_____________________________________________________________")