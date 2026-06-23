# Incident Response Plan

## Overview
When SentientShield AI detects anomalous network drift or high-risk connections, it triggers an alert and optionally queues a process intervention request for analyst approval.

## Alert Triage Workflow
1. **Detection:** The system highlights anomalous traffic in the "Operational Dashboard" and plots the geographic origin in the "Global Threat Intelligence" topology map.
2. **Analysis:** The analyst identifies the offending application (e.g., an unauthorized payload beaconing to a known malicious ASN).
3. **Approval:** The system generates an `AnalystApproval` request. The analyst navigates to the "Analyst Approvals" queue.
4. **Action:**
   - **Approve:** The OSBridge executes the sanction (suspend/terminate).
   - **Reject:** The action is canceled, and the heuristic model adjusts its threshold via the shadow validation loop to prevent future false positives.

## Emergency Fail-Safe
If the system becomes overly aggressive (e.g., due to model poisoning), administrators can halt autonomous recommendations:
1. Navigate to Settings.
2. Disable "Autonomous Threat Response" or lower the sensitivity slider.
3. Review the `HistoricalLogs` table to audit prior actions.
