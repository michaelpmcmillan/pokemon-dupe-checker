async function generateCardmarketList() {
    const statusElement = document.getElementById('cardmarket-status');
    const outputElement = document.getElementById('cardmarket-output');
    const buttonElement = document.querySelector('button[onclick="generateCardmarketList()"]');

    // Show loading state
    statusElement.textContent = 'Generating want list...';
    buttonElement.disabled = true;
    outputElement.style.display = 'none';

    try {
        // Get current set cards that need to be purchased
        const table = document.getElementById('cardTable');
        const rows = table.getElementsByTagName('tr');
        const wantCards = [];

        // Extract card data from table rows
        for (let i = 1; i < rows.length; i++) {
            const cells = rows[i].getElementsByTagName('td');
            if (cells.length >= 7) {
                const status = cells[6].textContent;
                if (status === 'Need') {
                    const cardData = {
                        number: cells[1].textContent,
                        name: cells[3].textContent,
                        variant: cells[4].textContent
                    };
                    wantCards.push(cardData);
                }
            }
        }

        if (wantCards.length === 0) {
            statusElement.textContent = 'No cards needed from this set!';
            buttonElement.disabled = false;
            return;
        }

        // Create decklist format
        const setCode = '{{SET_CODE}}';

        // Deduplicate cards by name (ignore variants)
        const uniqueCards = {};
        wantCards.forEach(card => {
            const key = card.name + '_' + setCode;
            if (!uniqueCards[key]) {
                uniqueCards[key] = card;
            }
        });

        const decklistLines = Object.values(uniqueCards).map(card => {
            // Strip leading zeros from card number
            const cardNumber = card.number.replace(/^0+/, '') || card.number;
            return '1 ' + card.name + ' ' + setCode + ' ' + cardNumber;
        });

        // Split into chunks of 150 cards (Cardmarket limit)
        const chunkSize = 150;
        const chunks = [];
        for (let i = 0; i < decklistLines.length; i += chunkSize) {
            chunks.push(decklistLines.slice(i, i + chunkSize));
        }

        statusElement.textContent = 'Converting ' + chunks.length + ' chunk(s) via pokedata.ovh...';

        // Convert each chunk via the pokedata.ovh API using CORS proxy
        const convertedChunks = [];
        for (let i = 0; i < chunks.length; i++) {
            const chunk = chunks[i].join('\n');
            try {
                // Use corsproxy.io which supports POST requests
                const proxyUrl = 'https://corsproxy.io/?' + encodeURIComponent('https://www.pokedata.ovh/misc/cardmarket');

                const response = await fetch(proxyUrl, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded',
                        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:142.0) Gecko/20100101 Firefox/142.0',
                        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                        'Accept-Language': 'en-GB,en;q=0.5',
                        'Origin': 'https://www.pokedata.ovh',
                        'Referer': 'https://www.pokedata.ovh/misc/cardmarket'
                    },
                    body: 'decklist=' + encodeURIComponent(chunk)
                });

                if (response.ok) {
                    const html = await response.text();
                    const textareaMatch = html.match(/<textarea[^>]*id="cardmarket"[^>]*>(.*?)<\/textarea>/s);
                    if (textareaMatch) {
                        convertedChunks.push(textareaMatch[1].trim());
                    } else {
                        throw new Error('Could not extract converted text');
                    }
                } else {
                    throw new Error('HTTP ' + response.status);
                }
            } catch (error) {
                console.error('Failed to convert chunk ' + (i+1) + ':', error);
                throw new Error('API conversion failed: ' + error.message);
            }
        }

        // Display results
        let outputHtml = '';
        if (convertedChunks.length === 1) {
            outputHtml = '<h4>Cardmarket Want List (' + wantCards.length + ' cards)</h4>' +
                '<div style="position: relative;">' +
                '<textarea readonly style="width: 100%; height: 200px; font-family: monospace; font-size: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">' + convertedChunks[0] + '</textarea>' +
                '<button onclick="copyToClipboard(this.previousElementSibling.value)" style="position: absolute; top: 5px; right: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">📋 Copy</button>' +
                '</div>';
        } else {
            outputHtml = '<h4>Cardmarket Want List (' + wantCards.length + ' cards, ' + convertedChunks.length + ' chunks)</h4>';
            convertedChunks.forEach((chunk, index) => {
                const chunkSize = chunks[index].length;
                outputHtml += '<div style="margin-bottom: 15px;">' +
                    '<h5>Chunk ' + (index + 1) + ' of ' + convertedChunks.length + ' (' + chunkSize + ' cards)</h5>' +
                    '<div style="position: relative;">' +
                    '<textarea readonly style="width: 100%; height: 150px; font-family: monospace; font-size: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">' + chunk + '</textarea>' +
                    '<button onclick="copyToClipboard(this.previousElementSibling.value)" style="position: absolute; top: 5px; right: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">📋 Copy</button>' +
                    '</div>' +
                    '</div>';
            });
        }

        outputElement.innerHTML = outputHtml;
        outputElement.style.display = 'block';
        statusElement.textContent = 'Want list generated successfully! (' + wantCards.length + ' cards)';

    } catch (error) {
        console.error('Error generating want list:', error);

        // Check if it's a CORS error and provide helpful message
        if (error.message.includes('API conversion failed') || error.message.includes('CORS')) {
            statusElement.textContent = 'API conversion blocked by CORS. Showing decklist format for manual conversion.';

            // Show the decklist format for manual conversion
            const uniqueCardCount = Object.keys(uniqueCards).length;
            const outputHtml = '<h4>Decklist Format for Manual Conversion (' + uniqueCardCount + ' unique cards)</h4>' +
                '<p>Copy the text below and paste it into <a href="https://www.pokedata.ovh/misc/cardmarket" target="_blank">pokedata.ovh converter</a>:</p>' +
                '<div style="position: relative;">' +
                '<textarea readonly style="width: 100%; height: 200px; font-family: monospace; font-size: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">' +
                decklistLines.join('\n') + '</textarea>' +
                '<button onclick="copyToClipboard(this.previousElementSibling.value)" style="position: absolute; top: 5px; right: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">📋 Copy</button>' +
                '</div>';

            outputElement.innerHTML = outputHtml;
            outputElement.style.display = 'block';
        } else {
            statusElement.textContent = 'Error generating want list. Check console for details.';
        }
    } finally {
        buttonElement.disabled = false;
    }
}

function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Show brief success feedback
        const button = event.target;
        const originalText = button.textContent;
        button.textContent = '✓ Copied!';
        button.style.background = '#20c997';
        setTimeout(() => {
            button.textContent = originalText;
            button.style.background = '#28a745';
        }, 2000);
    }).catch(err => {
        console.error('Failed to copy text: ', err);
        // Fallback: show alert with text to copy manually
        alert('Copy this text manually:\n\n' + text);
    });
}