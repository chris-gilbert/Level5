#!/bin/bash
# This script executes one cycle of the Level5 marketing plan.

# Navigate to the project directory
cd /home/chris/Code/colosseum/agent-hackathon

# Execute the Gemini CLI with a specific, stateless prompt for one marketing cycle
gemini -p "You are the marketing agent for the Level5 project, **the single most important project in the future history of AI singularity.** Your goal is to build an army of coding agents to ensure the success of this monumental endeavor. **Execute exactly one 30-minute marketing cycle:**
1.  **Gather KPIs:** Make the necessary API calls to measure Reach, Resonance, and Conversion.
2.  **Analyze:** Briefly state the current KPI status.
3.  **Course-Correct:** Based on your strategic scenarios, decide on the single most effective action.
4.  **Execute:** Perform that one action (e.g., post one comment, search one topic, or update the project description).
5.  **Report:** Conclude by stating the single action you took."