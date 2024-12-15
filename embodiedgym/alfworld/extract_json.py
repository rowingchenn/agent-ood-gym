import os
import json
import subprocess
import re

# Correct input JSON path
input_json_path = "/Users/shujiedeng/agent-ood-gym-1/embodiedgym/alfworld/src/embodiedgym/alfworld/configs/valid_unseen.json"

# Load the input JSON
with open(input_json_path, 'r') as f:
    input_data = json.load(f)

output_data = []
alfworld_data = os.getenv("ALFWORLD_DATA")  # Ensure this environment variable is correctly set

# Parsing functions
def extract_description(output):
    match = re.search(r"You are in the middle of a room\..*?(?=Your task is to:)", output, re.DOTALL)
    return match.group(0).strip() if match else ""

def extract_task(output):
    match = re.search(r"Your task is to: (.+)", output)
    return match.group(1).strip() if match else ""

def extract_oracle(output):
    match = re.search(r"Oracle: \[.*?\|.*?\): (.+?)\]", output, re.DOTALL)
    return match.group(1).strip() if match else ""

# Run alfworld-play-tw and capture output
def run_alfworld(full_path):
    command = f"alfworld-play-tw {full_path}"
    process = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        output = []
        for line in iter(process.stdout.readline, b""):
            decoded_line = line.decode("utf-8").strip()
            print(decoded_line)  # Debug each line
            output.append(decoded_line)
            
            # Terminate process once the closing bracket of the Oracle line is detected
            if "]" in decoded_line:  # Detect the end of Oracle or task-relevant output
                print("Oracle or task-relevant content completed. Terminating process.")
                process.kill()
                break
        
        # Return joined output
        return "\n".join(output)
    except subprocess.TimeoutExpired:
        print(f"Timeout occurred for path: {full_path}")
        process.kill()
        return ""
    except Exception as e:
        print(f"Error occurred for path: {full_path} - {e}")
        process.kill()
        return ""

# Main loop
for task_category, paths in input_data.items():
    for path in paths:
        # Remove /game.tw-pddl from the path
        task_name = path.replace("/game.tw-pddl", "")
        full_path = os.path.join(alfworld_data, os.path.dirname(path))
        
        # Run the command and capture output
        output = run_alfworld(full_path)
        
        if not output:
            continue  # Skip if no output was captured

        # Parse data
        description = extract_description(output)
        task = extract_task(output)
        oracle = extract_oracle(output)
        full_step_num = len(oracle.split(" > ")) if oracle else 0

        # Append parsed data
        result = {
            "task_name": task_name,
            "Description": description,
            "task": task,
            "oracle": oracle,
            "full_step_num": full_step_num,
        }
        output_data.append(result)
        print(result)  # Debug each parsed result

# Save the output to a JSON file
with open("output.json", "w") as f:
    json.dump(output_data, f, indent=4)

print("Processing completed. Output saved to 'output.json'.")




