const apiUrl = '/api/convert'; // API endpoint for conversion

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const convertButton = document.getElementById('convert-button');
    const statusMessage = document.getElementById('status-message');

    convertButton.addEventListener('click', async () => {
        const file = fileInput.files[0];
        if (!file) {
            statusMessage.textContent = 'Please select an EPUB file.';
            return;
        }

        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) {
                throw new Error('Conversion failed');
            }

            const result = await response.json();
            statusMessage.textContent = `Conversion successful! Download your file: ${result.downloadUrl}`;
        } catch (error) {
            statusMessage.textContent = `Error: ${error.message}`;
        }
    });
});