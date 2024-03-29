var socket = io(); // This line should be at the top of your scripts.js file

// Initialize an array to hold the lines
var logEntries = [];
const maxDisplayLines = 300;

// Function to open the fight creation form in modal
function openFightModal(accountId, characterId) {
    fetch('/paths')
        .then(response => response.json())
        .then(data => {
            const pathsSelect = document.getElementById('fightPathsSelect');
            pathsSelect.innerHTML = ''; // Clear previous options
            
            // Iterate over the paths object
            data.paths.forEach(pathLabel => {
                // Create an option element with the path name (key) as the label and the path value as the value
                let option = new Option(pathLabel.replace(/_/g, ' '), pathLabel); // Replace underscores with spaces for better readability
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
        accountId: accountId,
        characterId: characterId,
        pathId: pathValue,
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


function runTreasurehunt(accountId, characterId) {
    fetch(`/treasurehunt/${accountId}/${characterId}`)
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
    // Show the spinner
    document.getElementById('spinner').style.display = 'block';
    document.getElementById('import_accounts_button').style.display = 'none';
    document.getElementById('accounts-lis').innerHTML = '';

    fetch('/import_accounts')
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json(); // or .text() if the response is not JSON
    })
    .then(data => {
        console.log('Import successful:', data);
        // Hide the spinner
        document.getElementById('spinner').style.display = 'none';
        // You can refresh the page or update the UI here
        location.reload(); // Refreshes the page to update the accounts list
    })
    .catch(error => {
        console.error('Import failed:', error);
        // Hide the spinner even on failure
        document.getElementById('spinner').style.display = 'none';
        document.getElementById('import_accounts_button').style.display = 'block';
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
                    <tr class="${bot.status == 'BANNED' ? 'banned' : ''}">
                        <td>${bot.character}</td>
                        <td>${bot.level}</td>
                        <td>${bot.kamas}</td>
                        <td>${bot.pods}%</td>
                        <td>${bot.fights_count}</td>
                        <td>${bot.earned_kamas}</td>
                        <td>${bot.earned_levels}</td>
                        <td>${bot.path_name}</td>
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

// session stuff
function populatePathsDropdown(paths) {
    const pathsSelect = document.getElementById('pathsSelect');
    pathsSelect.innerHTML = ''; // Clear previous options
    console.log(paths);
    paths.forEach(pathLabel => {
        let option = new Option(pathLabel, pathLabel); // Using pathLabel as both the text and value
        pathsSelect.add(option);
    });
}

function adjustFormForSessionType(selectedType) {
    // Example: Show/hide "Add Path" button based on selected session type
    const addPathButton = document.getElementById('addPathButton');
    if (selectedType === 'MULTIPLE_PATHS_FARM') {
        addPathButton.style.display = 'block';
    } else {
        addPathButton.style.display = 'none';
    }
}

function submitFarmForm() {
    const accountId = document.getElementById('farmAccountId').value;
    const characterId = document.getElementById('farmCharacterId').value;
    const number_of_covers = document.getElementById('number_of_covers').value;

    // Initialize your session object
    let sessionData = {
        accountId: accountId,
        characterId: characterId,
        number_of_covers: number_of_covers,
        type: parseInt(document.getElementById('sessionTypeSelect').value),
        jobFilters: getSelectedJobsAndResources()
    };

    // Check the session type and add either a single path or a pathList
    if (sessionData.type == 7) {
        // Collect all selected options from the pathsSelect element
        const selectedPaths = Array.from(document.getElementById('pathsSelect').selectedOptions).map(option => option.value);
        sessionData.pathsIds = selectedPaths;
    } else {
        // Get the single selected path from the pathsSelect element
        const selectedPath = document.getElementById('pathsSelect').value;
        sessionData.pathId = selectedPath;
    }

    // Convert session object to JSON and POST it
    fetch('/farm', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(sessionData)
    }).then(response => {
        console.log('Success:', response);
        closeFarmModal();
    }).catch(error => {
        console.error('Error:', error);
    });
};

function openFarmModal(accountId, characterId) {
    fetch('/farm')
        .then(response => response.json())
        .then(data => {
            const sessionTypeSelect = document.getElementById('sessionTypeSelect');
            sessionTypeSelect.innerHTML = ''; // Clear previous options
            
            // Populate session types
            data.sessionTypes.forEach(stype => {
                let option = new Option(stype.label.replace(/_/g, ' '), stype.value);
                sessionTypeSelect.add(option);
            });

            // Listener for session type changes
            sessionTypeSelect.addEventListener('change', function() {
                populatePathsDropdown(data.paths);
            });

            // Adjust form and populate paths initially
            adjustFormAndPopulatePaths(sessionTypeSelect.value, data);

            // Combined listener for session type changes
            sessionTypeSelect.addEventListener('change', function() {
                adjustFormAndPopulatePaths(parseInt(this.value), data);
            });

            // Set hidden inputs for account and character ID
            document.getElementById('farmAccountId').value = parseInt(accountId);
            document.getElementById('farmCharacterId').value = parseFloat(characterId);

            // Show the modal
            document.getElementById('farmModal').style.display = 'block';
        })
        .catch(error => console.log('Error fetching farm data:', error));
}


function adjustFormAndPopulatePaths(selectedType, data) {
    // Check if the selected value is "MULTIPLE PATHS FARM"
    if (selectedType == 7) {
        // Change the select to allow multiple selections
        document.getElementById('pathsSelect').setAttribute('multiple', '');
        document.getElementById('pathsSelect').size = 5; // Show multiple rows
    } else {
        // Revert back to single selection
        document.getElementById('pathsSelect').removeAttribute('multiple');
        document.getElementById('pathsSelect').size = 1; // Show single row
    }    
    populatePathsDropdown(data.paths);
    const container = document.getElementById('jobFiltersContainer');
    container.innerHTML = ''; // Clear previous job filters
    data.skills.forEach(job => {
        addJobAndResourcesToForm(job);
    });
}

function addJobAndResourcesToForm(jobData) {
    const container = document.getElementById('jobFiltersContainer');
    const jobResourceGroup = document.createElement('div');
    jobResourceGroup.classList.add('job-resource-group');

    // Create a checkbox for the job
    const jobCheckbox = document.createElement('input');
    jobCheckbox.type = 'checkbox';
    jobCheckbox.id = `job-${jobData.id}`;
    jobCheckbox.value = jobData.id;
    jobCheckbox.name = 'jobs[]';
    
    // Event listener to toggle the disabled class
    jobCheckbox.addEventListener('change', function() {
        if (this.checked) {
            jobLabel.classList.remove('disabled');
            resourcesSelect.classList.remove('disabled');
        } else {
            jobLabel.classList.add('disabled');
            resourcesSelect.classList.add('disabled');
        }
    });

    // Create a label for the job name
    const jobLabel = document.createElement('label');
    jobLabel.htmlFor = `job-${jobData.id}`;
    jobLabel.textContent = jobData.name;
    jobLabel.classList.add('disabled'); // Start as disabled

    // Create a select element for resources
    const resourcesSelect = document.createElement('select');
    resourcesSelect.id = `resources-for-job-${jobData.id}`;
    resourcesSelect.multiple = true;
    resourcesSelect.name = `resources[${jobData.id}][]`;
    resourcesSelect.classList.add('disabled'); // Start as disabled

    // Fill the select element with options
    jobData.gatheredRessources.forEach(resource => {
        const option = document.createElement('option');
        option.value = resource.id;
        option.textContent = `${resource.name} (Level Min: ${resource.levelMin})`;
        resourcesSelect.appendChild(option);
    });

    // Append the elements to the group container
    jobResourceGroup.appendChild(jobCheckbox);
    jobResourceGroup.appendChild(jobLabel);
    jobResourceGroup.appendChild(resourcesSelect);
    
    // Append the group to the main container
    container.appendChild(jobResourceGroup);
}

function getSelectedJobsAndResources() {
    const selectedJobs = [];
    const jobCheckboxes = document.querySelectorAll('.job-resource-group input[type="checkbox"]:checked');

    jobCheckboxes.forEach(checkbox => {
        const jobId = checkbox.value;
        const resourcesSelect = document.getElementById(`resources-for-job-${jobId}`);
        const selectedResources = Array.from(resourcesSelect.options)
            .filter(option => option.selected)
            .map(option => option.value);

        selectedJobs.push({
            jobId: jobId,
            resourcesIds: selectedResources
        });
    });

    return selectedJobs;
}

// Function to close the modal
function closeFarmModal() {
    document.getElementById('farmModal').style.display = 'none';
}
