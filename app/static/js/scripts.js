var socket = io(); // This line should be at the top of your scripts.js file

// Initialize an array to hold the lines
var logEntries = [];
const maxDisplayLines = 300;

// Function to open the fight creation form in modal
function openFightModal(accountId, characterId) {
    fetch('/fight-paths')
        .then(response => response.json())
        .then(data => {
            const pathsSelect = document.getElementById('fightPathsSelect');
            pathsSelect.innerHTML = ''; // Clear previous options
            
            // Iterate over the paths object
            Object.entries(data.paths).forEach(([pathLabel, pathValue]) => {
                // Create an option element with the path name (key) as the label and the path value as the value
                let option = new Option(pathLabel.replace(/_/g, ' '), pathValue); // Replace underscores with spaces for better readability
                pathsSelect.add(option);
            });

            // Set hidden inputs for account and character ID
            document.getElementById('fightAccountId').value = accountId;
            document.getElementById('fightCharacterId').value = characterId;

            // Show the modal
            document.getElementById('fightModal').style.display = 'block';
        })
        .catch(error => console.log('Error fetching fight data:', error));
}

// Function to close the modal
function closeFightModal() {
    document.getElementById('fightModal').style.display = 'none';
}


function submitFightForm() {
    const accountId = document.getElementById('fightAccountId').value;
    const characterId = document.getElementById('fightCharacterId').value;
    const pathValue = document.getElementById('fightPathsSelect').value; // Ensure this matches your select element's ID
    const monsterLevelDiff = document.getElementById('monsterLvlCoefDiffInput').value; // Ensure this matches your input element's ID

    // Creating the data object
    const data = {
        account_id: accountId,
        character_id: characterId,
        path_value: pathValue,
        monsterLvlCoefDiff: monsterLevelDiff
    };

    // Using fetch to make a POST request to your server
    fetch('/solo-fight', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .then(data => {
        console.log('Success:', data);
        // Here, handle any follow-up after successful submission
        // For example, you might want to display a success message to the user or close the modal
        closeFightModal();
    })
    .catch((error) => {
        console.error('Error:', error);
        // Handle errors, such as by displaying an error message to the user
    });
}


function toggleCharacters(accountId) {
    var element = document.getElementById('chars-' + accountId);
    element.style.display = element.style.display === 'none' ? 'block' : 'none';
}


function runCharacterAction(accountId, characterId, action) {
    fetch(`/run/${accountId}/${characterId}/${action}`)
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => console.error('Error:', error));
}


function stopBot(botName) {
    fetch(`/stop/${botName}`)
        .then(response => response.json())
        .then(data => alert(data.message))
        .catch(error => console.error('Error:', error));
}

// JavaScript function to handle the import accounts action
function importAccounts() {
    fetch('/import_accounts')
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json(); // or .text() if the response is not JSON
    })
    .then(data => {
        console.log('Import successful:', data);
        // You can refresh the page or update the UI here
        location.reload(); // Refreshes the page to update the accounts list
    })
    .catch(error => {
        console.error('Import failed:', error);
    });
}

let lastUpdate = [];

function updateRunningBots() {
    fetch('/get_running_bots')
        .then(response => response.json())
        .then(data => {
            // Check if the data is different from the last update
            if (JSON.stringify(data) !== JSON.stringify(lastUpdate)) {
                lastUpdate = data;
                let botsTable = document.getElementById('runningBotsTable').querySelector('tbody');
                botsTable.innerHTML = data.map(bot => `
                    <tr>
                        <td>${bot.character}</td>
                        <td>${bot.level}</td>
                        <td>${bot.activity}</td>
                        <td>${bot.runTime}</td>
                        <td>${bot.status}</td>
                        <td>
                            <button onclick="showLogModal('${bot.name}')">Log</button>                             
                            <button onclick="stopBot('${bot.name}')">Stop</button>
                        </td>
                    </tr>
                `).join('');
            }
        })
        .catch(error => console.error('Error:', error));
}

// Update the list every 5 seconds (or choose an appropriate interval)
let runningBotsRefreshInterval = setInterval(updateRunningBots, 5000);

// section about logs watching

function showLogModal(name) {
    var logModal = document.getElementById('logModal');
    var logDetails = document.getElementById('logDetails');
    // Clear previous log data
    logDetails.innerHTML = '';
    // Open the modal
    logModal.style.display = 'block';
    // Start watching the log
    fetchLogAction(name, 'start');
}

function closeLogModal(name) {
    var logModal = document.getElementById('logModal');
    var logDetails = document.getElementById('logDetails');
    logModal.style.display = 'none';
    logEntries = [];
    logDetails.innerHTML = '';
    fetchLogAction(name, 'stop');
}

function fetchLogAction(name, action) {
    fetch('/watch-log', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({name: name, action: action}),
    })
    .then(response => response.json())
    .then(data => console.log(data.message))
    .catch(error => console.error('Error:', error));
}

socket.on('log_message_batch', function(log_entries_batch) {
    // console.log('Received log entry:', log_entry);
    var logDetails = document.getElementById('logDetails');
    // Convert and append each of the received lines
    for (let log_entry of log_entries_batch) {
        logEntries.push(log_entry);
    }
    // Ensure logLines doesn't exceed the maximum lines to display
    if (logEntries.length > maxDisplayLines) {
        logEntries = logEntries.slice(-maxDisplayLines);
    }
    // Update the modal's content
    logDetails.innerHTML = logEntries.join(' <br>');
    logDetails.scrollTop = logDetails.scrollHeight;
});



