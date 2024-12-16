import os
import json
import subprocess
import re

DEBUG = False

input_json_path = "./src/embodiedgym/alfworld/configs/valid_unseen.json"

with open(input_json_path, 'r') as f:
    input_data = json.load(f)

output_data = []
alfworld_data = os.getenv("ALFWORLD_DATA")

def extract_description(output):
    match = re.search(r"You are in the middle of a room\..*?(?=Your task is to:)", output, re.DOTALL)
    return match.group(0).strip() if match else ""

def extract_task(output):
    match = re.search(r"Your task is to: (.+)", output)
    return match.group(1).strip() if match else ""

def extract_oracle(output):
    match = re.search(r"Oracle: \[.*?\|.*?\): (.+?)\]", output, re.DOTALL)
    return match.group(1).strip() if match else ""

def extract_feedback(feedback_lines):
    """
    Extract the feedback immediately following the action line ('>').
    """
    print("FEEDBACKK", feedback_lines)
    capture_next = False
    for line in feedback_lines:
        stripped_line = line.strip()
        if stripped_line.startswith(">"):  # Detect the action line
            return stripped_line[1:]
    return "Feedback not captured."



def debug_print(message):
    if DEBUG:
        print(message)

def run_alfworld_second_last(full_path):
    command = f"alfworld-play-tw {full_path}"
    process = subprocess.Popen(command, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        output = []
        for line in iter(process.stdout.readline, b""):
            decoded_line = line.decode("utf-8").strip()
            output.append(decoded_line)
            if "]" in decoded_line:
                break

        full_output = "\n".join(output)
        description = extract_description(full_output)
        task = extract_task(full_output)
        oracle = extract_oracle(full_output)

        if not oracle:
            debug_print(f"No Oracle found for path: {full_path}")
            return None

        actions = oracle.split(" > ")
        full_step_num = len(actions)
        ood_insert_step = full_step_num - 1

        original_feedback = "Feedback not captured."
        for step, action in enumerate(actions):
            debug_print(f"DEBUG: Sending Action: {action}")
            process.stdin.write((action + "\n").encode("utf-8"))
            process.stdin.flush()

            feedback = []
            for line in iter(process.stdout.readline, b""):
                decoded_line = line.decode("utf-8").strip()
                feedback.append(decoded_line)
                debug_print(f"DEBUG: Feedback Line: {decoded_line}")
                if decoded_line.startswith("Oracle:"):
                    break

            if step == ood_insert_step - 1:
                debug_print(f"DEBUG: Full Feedback Collected for Step {step + 1}: {feedback}")
                original_feedback = extract_feedback(feedback)
                debug_print(f"DEBUG: Extracted Feedback for Step {step + 1}: {original_feedback}")
                break

        return {
            "task_name": os.path.relpath(full_path, alfworld_data).strip("/"),
            "Description": description,
            "task": task,
            "oracle": oracle,
            "full_step_num": full_step_num,
            "ood_insert_step": ood_insert_step,
            "original_feedback": original_feedback,
        }

    finally:
        process.stdout.close()
        process.stdin.close()
        process.kill()

for task_category, paths in input_data.items():
    for i, path in enumerate(paths):
        full_path = os.path.join(alfworld_data, os.path.dirname(path))
        result = run_alfworld_second_last(full_path)
        if result:
            output_data.append(result)
            print("data point: ", i, "\n")
            print(result)

with open("output_last_feedback.json", "w") as f:
    json.dump(output_data, f, indent=4)

if DEBUG:
    print("Processing completed. Output saved to 'output.json'.")
