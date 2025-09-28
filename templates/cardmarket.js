function generateCardmarketList() {
    const statusElement = document.getElementById('cardmarket-status');
    const outputElement = document.getElementById('cardmarket-output');
    const buttonElement = document.querySelector('button[onclick="generateCardmarketList()"]');

    // Show loading state
    statusElement.textContent = 'Generating want list...';
    buttonElement.disabled = true;
    outputElement.style.display = 'none';

    try {
        // Get currently visible cards that need to be purchased
        const table = document.getElementById('cardTable');
        const rows = table.getElementsByTagName('tr');
        const wantCards = [];

        // Extract card data from visible table rows only
        for (let i = 1; i < rows.length; i++) {
            const row = rows[i];
            const cells = row.getElementsByTagName('td');

            // Only process visible rows that need cards
            if (row.style.display !== 'none' && cells.length >= 8) {
                const status = cells[7].textContent;
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
            statusElement.textContent = 'No cards needed from the currently filtered view!';
            buttonElement.disabled = false;
            return;
        }

        // Create decklist format
        const setCode = '{{SET_CODE}}';

        // Deduplicate cards by name and number (ignore variants only)
        const uniqueCards = {};
        wantCards.forEach(card => {
            const key = card.name + '_' + card.number + '_' + setCode;
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

        // Process all chunks
        const uniqueCardCount = Object.keys(uniqueCards).length;

        if (chunks.length === 1) {
            // Single chunk - try API conversion
            statusElement.textContent = 'Testing API conversion...';
            const chunk = chunks[0].join('\n');

            fetch('https://corsproxy.io/?' + encodeURIComponent('https://www.pokedata.ovh/misc/cardmarket'), {
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
            })
            .then(response => {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                return response.text();
            })
            .then(html => {
                // Check if we got the form page or actual conversion
                const textareaMatch = html.match(/<textarea[^>]*id="cardmarket"[^>]*>(.*?)<\/textarea>/s);
                if (textareaMatch && textareaMatch[1].trim()) {
                    // Success! Show converted result
                    statusElement.textContent = 'API conversion successful!';
                    const convertedText = textareaMatch[1].trim();

                    const outputHtml = '<h4>Cardmarket Want List (' + uniqueCardCount + ' cards)</h4>' +
                        '<p style="color: #28a745; margin-bottom: 15px;">✅ Automatically converted with abilities included!</p>' +
                        '<div style="position: relative;">' +
                        '<textarea readonly style="width: 100%; height: 200px; font-family: monospace; font-size: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">' + convertedText + '</textarea>' +
                        '<button onclick="copyToClipboard(this.previousElementSibling.value)" style="position: absolute; top: 5px; right: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">📋 Copy</button>' +
                        '</div>';

                    outputElement.innerHTML = outputHtml;
                    outputElement.style.display = 'block';
                } else {
                    throw new Error('No converted text found');
                }
            })
            .catch(error => {
                // Fallback to manual conversion for single chunk
                console.log('API conversion failed, showing manual format:', error);
                showManualConversion();
            });
        } else {
            // Multiple chunks - skip API and show manual conversion with chunks
            statusElement.textContent = 'Multiple chunks needed (>150 cards), using manual format';
            showManualConversionWithChunks();
        }

        function showManualConversion() {
            const outputHtml = '<h4>Manual Conversion Required (' + uniqueCardCount + ' cards)</h4>' +
                '<p style="margin-bottom: 15px;">API conversion failed. Copy the decklist below and convert it manually:</p>' +
                '<div style="margin-bottom: 15px; padding: 15px; background-color: #e7f3ff; border-radius: 5px; border-left: 4px solid #007bff;">' +
                '<strong>📋 Step 1:</strong> Copy the decklist below<br>' +
                '<strong>🔗 Step 2:</strong> <a href="https://www.pokedata.ovh/misc/cardmarket" target="_blank" style="color: #007bff; font-weight: bold;">Open pokedata.ovh converter</a><br>' +
                '<strong>📝 Step 3:</strong> Paste the decklist and click "Convert"<br>' +
                '<strong>✅ Step 4:</strong> Copy the result to Cardmarket' +
                '</div>' +
                '<div style="position: relative;">' +
                '<textarea readonly style="width: 100%; height: 200px; font-family: monospace; font-size: 12px; padding: 10px; border: 1px solid #ddd; border-radius: 4px;">' +
                decklistLines.join('\n') + '</textarea>' +
                '<button onclick="copyToClipboard(this.previousElementSibling.value)" style="position: absolute; top: 5px; right: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">📋 Copy Decklist</button>' +
                '</div>';

            outputElement.innerHTML = outputHtml;
            outputElement.style.display = 'block';
        }

        function showManualConversionWithChunks() {
            let outputHtml = '<h4>Multiple Want Lists Required (' + uniqueCardCount + ' cards total)</h4>' +
                '<p style="margin-bottom: 15px; color: #dc3545;"><strong>⚠️ Important:</strong> Cardmarket limits want lists to 150 cards. Your filtered selection has been split into ' + chunks.length + ' separate lists.</p>' +
                '<div style="margin-bottom: 15px; padding: 15px; background-color: #e7f3ff; border-radius: 5px; border-left: 4px solid #007bff;">' +
                '<strong>📋 Step 1:</strong> Copy each decklist below (one at a time)<br>' +
                '<strong>🔗 Step 2:</strong> <a href="https://www.pokedata.ovh/misc/cardmarket" target="_blank" style="color: #007bff; font-weight: bold;">Open pokedata.ovh converter</a><br>' +
                '<strong>📝 Step 3:</strong> Paste each decklist and click "Convert"<br>' +
                '<strong>✅ Step 4:</strong> Copy each result to separate Cardmarket want lists' +
                '</div>';

            // Add each chunk as a separate panel
            chunks.forEach((chunk, index) => {
                const chunkText = chunk.join('\n');
                outputHtml += '<div style="margin-bottom: 20px; border: 1px solid #ddd; border-radius: 5px; overflow: hidden;">' +
                    '<div style="background-color: #f8f9fa; padding: 10px; border-bottom: 1px solid #ddd; font-weight: bold;">Want List ' + (index + 1) + ' of ' + chunks.length + ' (' + chunk.length + ' cards)</div>' +
                    '<div style="position: relative; padding: 0;">' +
                    '<textarea readonly style="width: 100%; height: 150px; font-family: monospace; font-size: 12px; padding: 10px; border: none; resize: vertical;">' + chunkText + '</textarea>' +
                    '<button onclick="copyToClipboard(this.previousElementSibling.value)" style="position: absolute; top: 5px; right: 5px; padding: 5px 10px; background: #28a745; color: white; border: none; border-radius: 3px; cursor: pointer; font-size: 12px;">📋 Copy List ' + (index + 1) + '</button>' +
                    '</div></div>';
            });

            outputElement.innerHTML = outputHtml;
            outputElement.style.display = 'block';
        }

    } catch (error) {
        console.error('Error generating want list:', error);
        statusElement.textContent = 'Error generating want list. Check console for details.';
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