// SPDX-License-Identifier: MIT
pragma solidity 0.8.19;

contract AuditTrail {

    // A structure to hold the details of a single log entry
    struct LogEntry {
        uint logId;
        string caseId;        // The Medico-Legal Case (MLC) ID
        string eventDetails;  // What happened, e.g., "Photos uploaded by Dr. B"
        uint timestamp;       // The time the log was added
        address loggedBy;     // The address that added this log
    }

    // A dynamic array to store all log entries
    LogEntry[] public allLogs;

    // An event that is emitted every time a new log is added
    // This makes it easy to "listen" for new logs from a frontend
    event LogAdded(
        uint indexed logId,
        string indexed caseId,
        string eventDetails,
        uint timestamp,
        address loggedBy
    );

    /**
     * @dev Adds a new audit log entry to the blockchain.
     * @param _caseId The ID of the Medico-Legal Case.
     * @param _eventDetails A description of the event to be logged.
     */
    function addLog(string memory _caseId, string memory _eventDetails) public {
        uint newLogId = allLogs.length;

        // Create the new log entry in memory
        LogEntry memory newEntry = LogEntry({
            logId: newLogId,
            caseId: _caseId,
            eventDetails: _eventDetails,
            timestamp: block.timestamp, // In-built global variable for time
            loggedBy: msg.sender         // In-built global variable for the caller
        });

        // Add it to the storage array
        allLogs.push(newEntry);

        // Emit an event to notify listeners
        emit LogAdded(newLogId, _caseId, _eventDetails, block.timestamp, msg.sender);
    }

    /**
     * @dev Returns the total number of logs stored.
     */
    function getLogCount() public view returns (uint) {
        return allLogs.length;
    }

    /**
     * @dev Retrieves a specific log entry by its index.
     * Note: This is for demonstration. For a real app, you'd filter by caseId
     * using events, as looping is inefficient.
     */
    function getLog(uint _index) public view returns (
        uint,
        string memory,
        string memory,
        uint,
        address
    ) {
        require(_index < allLogs.length, "Log index out of bounds");
        LogEntry storage entry = allLogs[_index];
        return (
            entry.logId,
            entry.caseId,
            entry.eventDetails,
            entry.timestamp,
            entry.loggedBy
        );
    }
}