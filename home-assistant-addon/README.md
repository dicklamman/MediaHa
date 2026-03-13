# Home Assistant EPUB Converter Add-on

This Home Assistant add-on provides a web interface for converting EPUB files to 香港繁體 (Hong Kong Traditional Chinese). Users can select books from the `/media/eBook` directory and initiate the conversion process.

## Features

- User-friendly web UI for selecting EPUB files.
- Converts selected EPUB files to Hong Kong Traditional Chinese.
- Easy integration with Home Assistant.

## Installation

1. Clone this repository to your Home Assistant add-ons directory.
2. Navigate to the add-on directory:
   ```
   cd home-assistant-addon
   ```
3. Build the Docker image:
   ```
   docker build -t home-assistant-addon .
   ```
4. Add the add-on to your Home Assistant instance through the UI.

## Usage

1. Access the add-on from the Home Assistant sidebar.
2. Select an EPUB file from the `/media/eBook` directory.
3. Click the "Convert" button to start the conversion process.
4. Download the converted file once the process is complete.

## Configuration

The add-on can be configured through the Home Assistant UI. Ensure that the `/media/eBook` directory is accessible and contains the EPUB files you wish to convert.

## Dependencies

This add-on requires the following Python packages:

- `ebooklib`
- `beautifulsoup4`
- `opencc`

These packages are installed automatically when building the Docker image.

## License

This project is licensed under the MIT License. See the LICENSE file for details.