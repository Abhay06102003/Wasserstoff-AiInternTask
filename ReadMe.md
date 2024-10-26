# PDF Processing Pipeline

A robust, scalable Python application for processing PDF documents with advanced text analysis capabilities. The pipeline extracts text, generates summaries, identifies keywords, and stores results in MongoDB, all while maintaining performance metrics and testing coverage.

## Features

- **Intelligent Text Processing**

  - Dynamic summary generation based on document length
  - Advanced keyword extraction with configurable thresholds
  - Named entity recognition for domain-specific terminology

- **Scalable Architecture**

  - Concurrent document processing using ThreadPoolExecutor
  - Configurable batch processing capabilities
  - Robust MongoDB integration with connection pooling

- **Performance Monitoring**

  - Real-time performance metrics tracking
  - Memory usage monitoring
  - Execution time analysis
  - Detailed logging system

- **Quality Assurance**
  - Comprehensive test suite with visualization
  - Content quality metrics
  - Performance benchmarking
  - Automated test reporting

## System Requirements

- Python 3.8+
- MongoDB 4.4+
- Docker (optional)
- Sufficient storage for PDF processing
- Memory requirements vary based on PDF sizes

## Dependencies


pymongo
spacy
PyPDF2
python-dotenv
psutil
matplotlib
pandas
numpy


## Installation Instructions

- Clone the repository `git clone https://github.com/Abhay06102003/wasserstoff-AiInternTask.git`
- `cp .env.example .env`
- fill the required fields in the `.env` file

- Manual Installation

  - `pip install -r requirements.txt`
  - `python main.py`
  - `python test.py`

- Docker Installation
  - `docker-compose up --build`

## Configuration

1. Create a `.env` file in the project root with:


`uri=your_mongodb_connection_string`


2. Customize `ProcessingConfig` in `main.py` for your needs:

python
SHORT_DOC_THRESHOLD = 10  # pages
MEDIUM_DOC_THRESHOLD = 50  # pages
SHORT_SUMMARY_RATIO = 0.25
MEDIUM_SUMMARY_RATIO = 0.2
LONG_SUMMARY_RATIO = 0.15


## Usage

1. **Basic Usage**

python
from main import PDFProcessor

processor = PDFProcessor(
    mongodb_uri="your_uri",
    db_name="your_db",
    collection_name="your_collection"
)

# Process single PDF
result = processor.process_single_pdf("path/to/pdf")

# Process entire folder
results = processor.process_folder("path/to/folder", max_workers=4)


2. **Running Tests**

bash
python -m unittest test.py -v


## Output Structure

Each processed document generates the following MongoDB structure:

json
{
  "_id": "ObjectId",
  "filename": "document.pdf",
  "file_path": "/path/to/file",
  "file_size": 1234567,
  "page_count": 42,
  "creation_date": "ISO-DATE",
  "processing_status": "completed",
  "summary": "Generated summary text...",
  "keywords": ["keyword1", "keyword2", "..."],
  "last_updated": "ISO-DATE"
}


## Performance Monitoring

The system generates detailed performance reports including:

- Processing time per document
- Memory usage metrics
- Visualization plots
- Quality metrics for processed content

Reports are saved as:

- `performance_report.json`: Detailed metrics
- `time_vs_size.png`: Processing time analysis
- `memory_usage.png`: Memory consumption analysis
- `quality_metrics.png`: Content quality visualization

## Error Handling

The system implements comprehensive error handling:

- MongoDB connection failures
- PDF processing errors
- Memory constraints
- Concurrent processing issues

All errors are logged to `pdf_pipeline.log` and `pipeline_test_results.log`

## Best Practices

1. Monitor system resources when processing large documents
2. Adjust `max_workers` based on available CPU cores
3. Regular monitoring of MongoDB connection pool
4. Periodic review of performance metrics
5. Backup database before large batch operations

## Contributing

1. Fork the repository
2. Create feature branch
3. Commit changes
4. Push to branch
5. Create Pull Request


## Contact

Abhay Chourasiya
21je0010@iitism.ac.in
9508197014