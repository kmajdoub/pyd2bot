document.getElementById('addSessionButton').addEventListener('click', function() {
    // Show modal to select player pseudo and session type
    // Populate modal content dynamically based on backend data
    showAddSessionModal();
});

function showAddSessionModal() {
    // This function will display the modal to add a session.
    // It needs to fetch player pseudos from the backend and display them as options.
    // Upon selecting a session type, it will adjust the form shown in the modal accordingly.
}

function submitSessionForm() {
    // This function will handle form submission.
    // It will collect form data and send a POST request to the /session endpoint.
}

function fetchSessions() {
    // Fetch existing sessions from the backend and display them in the #sessionsList div.
    // Each session should have Start/Stop/Delete buttons with event handlers.
}

// Call fetchSessions on page load to populate the list of existing sessions
fetchSessions();
