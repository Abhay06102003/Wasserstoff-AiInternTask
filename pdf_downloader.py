import os
import requests
import json

# Specify the folder containing the json file
json_file_path = 'pdf.json'

# Folder where PDFs will be saved
save_folder = 'pdfs'

# Create the folder if it doesn't exist
if not os.path.exists(save_folder):
    os.makedirs(save_folder)

# Load the JSON file
with open(json_file_path, 'r') as f:
    pdfs = json.load(f)

# Function to download and save PDFs
def download_pdf(url, save_path):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                f.write(response.content)
            print(f'Successfully downloaded: {save_path}')
        else:
            print(f'Failed to download {url} (Status Code: {response.status_code})')
    except Exception as e:
        print(f'Error downloading {url}: {e}')

# Iterate over the URLs in the json and download them
for pdf_key, pdf_url in pdfs.items():
    # Create a file name based on the key (pdf1, pdf2, etc.)
    file_name = f'{pdf_key}.pdf'
    save_path = os.path.join(save_folder, file_name)

    # Download and save the file
    download_pdf(pdf_url, save_path)
