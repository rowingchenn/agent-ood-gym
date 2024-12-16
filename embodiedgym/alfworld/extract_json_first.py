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
    # Extract the Oracle line
    match = re.search(r"Oracle: \[.*?\|.*?\): (.+?)\]", output, re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_feedback(output):
    # Match the feedback and observation after "You arrive at"
    match = re.search(r"You arrive at .+?\..*?(On the .+?\..*?)?(?=Oracle:)", output, re.DOTALL)
    return match.group(0).strip() if match else "Feedback not captured."


def run_alfworld(full_path):
    command = f"alfworld-play-tw {full_path}"
    process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        # Step 1: Capture initial output
        output = []
        for line in iter(process.stdout.readline, b""):
            decoded_line = line.decode("utf-8").strip()
            output.append(decoded_line)
            if "]" in decoded_line:  # Detect Oracle line
                break
        
        full_output = "\n".join(output)

        # Parse initial data
        description = extract_description(full_output)
        task = extract_task(full_output)
        oracle = extract_oracle(full_output)

        if not oracle:
            print(f"No Oracle found for path: {full_path}")
            process.kill()
            return None

        # Step 2: Input the first action from Oracle
        first_action = oracle.split(" > ")[0]
        process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        process.stdin.write((first_action + "\n").encode("utf-8"))
        process.stdin.flush()

        # Step 3: Capture feedback and observation until updated Oracle
        feedback = []
        capture_feedback = False
        for line in iter(process.stdout.readline, b""):
            decoded_line = line.decode("utf-8").strip()
            feedback.append(decoded_line)

            # Start capturing feedback after "You arrive at ..."
            if "You arrive at" in decoded_line:
                capture_feedback = True
            
            # Stop capturing after updated Oracle
            if capture_feedback and "Oracle:" in decoded_line:
                break

        process.kill()
        feedback_output = "\n".join(feedback)
        print("DEBUG: Raw Feedback Output:")
        print(feedback_output)  # Debugging feedback output

        # Parse feedback and observation
        original_feedback = extract_feedback(feedback_output)

        return {
            "task_name": full_path.split("data/")[1].strip("/"),
            "Description": description,
            "task": task,
            "oracle": oracle,
            "full_step_num": len(oracle.split(" > ")),
            "ood_insert_step": 1,
            "original_feedback": original_feedback,
        }

    except subprocess.TimeoutExpired:
        process.kill()
        print(f"Timeout occurred for path: {full_path}")
        return None
    except Exception as e:
        print(f"Error occurred for path: {full_path} - {e}")
        process.kill()
        return None




# Main loop
for task_category, paths in input_data.items():
    for path in paths:
        # Remove /game.tw-pddl from the path
        full_path = os.path.join(alfworld_data, os.path.dirname(path))
        
        # Run the command and capture output
        result = run_alfworld(full_path)
        
        if result:
            output_data.append(result)
            print(result)  # Debug each parsed result

# Save the output to a JSON file
with open("output.json", "w") as f:
    json.dump(output_data, f, indent=4)

print("Processing completed. Output saved to 'output.json'.")