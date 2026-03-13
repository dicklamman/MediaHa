const apiUrl = '/convert'; // API endpoint for conversion

document.addEventListener('DOMContentLoaded', () => {
    const conversionForm = document.getElementById('conversion-form');
    const fileSelect = document.getElementById('epub-file');
    const resultMessage = document.getElementById('result');

    conversionForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const fileName = fileSelect.value;
        if (!fileName) {
            resultMessage.textContent = 'Please select an EPUB file.';
            return;
        }

        resultMessage.textContent = 'Converting...';

        try {
            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ file_name: fileName }),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Conversion failed');
            }

            const result = await response.json();
            resultMessage.textContent = `Conversion successful! File saved to: ${result.output_file}`;
        } catch (error) {
            resultMessage.textContent = `Error: ${error.message}`;
        }
    });

    // Optional: Fetch the list of EPUB files from a new endpoint later
    // For now, it expects the user to type or have options populated.
});