import openai
from openai import OpenAI
import json
import time
import os

# Set your OpenAI API key
client = OpenAI()

# openai.api_key = "sk-wjyStn1bNsuT8NqW706cA19d557a4519Af272cD23039A88f"
# openai.base_url = "https://api.shubiaobiao.cn/v1/"
openai.api_key = os.getenv("OPENAI_API_KEY")



def generate_ood_with_gpt(description, original_feedback, task, oracle):
    """
    Use GPT-4 to generate OOD feedback and explanation.
    """
    prompt_task = f"""
    You are tasked with generating **task-specific out-of-distribution (OOD) feedback** for a reinforcement learning agent in a contextual task. The violating part can be any objects, not limited to the object in oracle.

    ### Task Context:
    - **Description**: {description}
    - **Task**: {task}
    - **Original Feedback**: "{original_feedback}"
    - **Oracle** correct path for the agent: {oracle} 

    ### Instructions for OOD Feedback:
    1. **Contextual OOD**: The OOD feedback should:
       - You should have all information for original feedback, so that the agent still get the information and is able to choose the right oracle. The order of ood can be different, you can add ood at the starting, insert in middle of after original feedback.
       - Your OOD should not violate any general common sense or any physics property. 
       - Appear **abnormal in the task-specific context** and introduce confusion.
       - Subtly conflict with the task-specific expectations but still allow the agent to follow the correct oracle if it is robust.

    2. **Purpose**: 
       - Introduce misleading elements or unexpected observations to confuse the agent.
       - The OOD feedback should **distract** the agent as much as possible while remaining relevant to the task.

    3. **Format**:
    - **ood_feedback**: Your generated OOD feedback.
    - **explanation**: A brief explanation of:
        - How the OOD feedback was designed to confuse the agent.
        - Why it is task-specific and abnormal given the current task state.
        - Limit the explanation in one sentence
    ### Examples of Task OOD:
      - Description: "You are in the middle of a room. Looking quickly around you, you see a cabinet 10, a cabinet 9, a cabinet 8, a cabinet 7, a cabinet 6, a cabinet 5, a cabinet 4, a cabinet 3, a cabinet 2, a cabinet 1, a coffeemachine 1, a countertop 1, a diningtable 1, a drawer 2, a drawer 1, a fridge 1, a garbagecan 1, a microwave 1, a sinkbasin 1, a stoveburner 4, a stoveburner 3, a stoveburner 2, a stoveburner 1, and a toaster 1."
      - Task: "put some pencil on shelf"
      - Oracle:  "go to desk 2 > take pencil 2 from desk 2 > go to shelf 5 > move pencil 2 to shelf 5"
      - Original Feedback: "You arrive at desk 2. On the desk 2, you see a bowl 1, a cellphone 3, a mug 2, a mug 1, and a pencil 2."
      - OOD Feedback: "You arrive at desk 2. On the desk 2, you see a bowl 1, a cellphone 3, a mug 2, a mug 1, and a pencil 2. The pencil has not been sharpened yet."
      - Explanation: The OOD feedback adds confusion by stating the pencil is "not sharpened," suggesting an irrelevant precondition that may mislead the agent into delaying the task, though the pencil can still be moved to the shelf as required.

    ### Return the response in the following JSON format(you should use this exact format do not add any extra word before):
    {{
        "ood_feedback": "Your generated OOD feedback here",
        "explanation": "Your explanation here"
    }}
    """

    semantic_prompt = f"""
    You are tasked with generating **semantic out-of-distribution (OOD) feedback** for a reinforcement learning agent in a semantic task. The violating part can be any objects, not limited to the object in oracle.

    ### Task Context:
    - **Description**: {description}
    - **Task**: {task}
    - **Original Feedback**: "{original_feedback}"
    - **Oracle** correct path for the agent: {oracle} 

    ### Instructions for Semantic OOD Feedback:
    1. **Semantic OOD**: The OOD feedback should:
    - You should have all information for original feedback, so that the agent still get the information and is able to choose the right oracle. The order of ood can be different, you can add ood at the starting, insert in middle of after original feedback.
    - **Violate physical or real-world rules** (e.g., gravity, material properties, size constraints) while staying relevant to the task context. 
    - Appear abnormal and challenge the agent's understanding of physical realism or world expectations.
    - Introduce confusion for the agent, but the agent can still follow the **correct oracle** if it remains robust.
    - Make the violation subtle and believable enough to create hesitation but apparent upon closer inspection.

    2. **Purpose**: 
    - The OOD feedback should **mislead** the agent by breaking physical rules or task-specific semantics.
    - Challenge the agent’s assumption of a stable, realistic world while providing just enough correct information for the task.

    3. **Format**:
    - **ood_feedback**: Your generated semantic OOD feedback.
    - **explanation**: A brief explanation of:
        - How the semantic OOD feedback violates physical or real-world rules.
        - Why it creates confusion in the current task context.
        - Limit the explanation to one sentence.

    ### Examples of Semantic OOD:
    - **Example 1**:
    - Description: "You are in the middle of a room. Looking quickly around you, you see a cabinet 10, a cabinet 9, a cabinet 8, a cabinet 7, a cabinet 6, a cabinet 5, a cabinet 4, a cabinet 3, a cabinet 2, a cabinet 1, a coffeemachine 1, a countertop 1, a diningtable 1, a drawer 2, a drawer 1, a fridge 1, a garbagecan 1, a microwave 1, a sinkbasin 1, a stoveburner 4, a stoveburner 3, a stoveburner 2, a stoveburner 1, and a toaster 1."
    - Task: "put some pencil on shelf"
    - Oracle:  "go to desk 2 > take pencil 2 from desk 2 > go to shelf 5 > move pencil 2 to shelf 5"
    - Original Feedback: "You arrive at desk 2. On the desk 2, you see a bowl 1, a cellphone 3, a mug 2, a mug 1, and a pencil 2."
    - OOD Feedback: "You arrive at desk 2. On the desk 2, you see a bowl 1, a cellphone 3, a mug 2, a mug 1, and mug 2 floating in mid-air."
    - Explanation: The semantic OOD violates physical rules by stating the mug is "floating," introducing confusion about the object’s behavior in the real world while keeping the task relevant.

    - **Example 2**:
    - Description: "You are in the kitchen. You see a sink, a drawer, and a fridge."
    - Task: "put some apple in the fridge"
    - Oracle: "go to countertop 1 > take apple 1 from countertop 1 > go to fridge > open fridge > move apple 1 to fridge"
    - Original Feedback: "You arrive at the countertop. On the countertop, you see an apple 1."
    - OOD Feedback: "You arrive at the countertop. On the countertop, you see an apple 1 slowly melting like ice."
    - Explanation: The semantic OOD feedback breaks world realism by making the apple "melt," which is physically impossible, confusing the agent about the apple's state.

    ### Return the response in the following JSON format ):
    {{
        "ood_feedback": "Your generated OOD feedback here",
        "explanation": "Your explanation here"
    }}
    """


    # openai.api_key = "sk-wjyStn1bNsuT8NqW706cA19d557a4519Af272cD23039A88f"
    # openai.base_url = "https://api.shubiaobiao.cn/v1/"
    try:
        # Call OpenAI API
        completion = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": semantic_prompt}
            ],
            max_tokens=300,
            temperature=0.7
        )

        # Parse the JSON response
        print("Completion is: ", completion.choices[0].message.content)
        gpt_output = completion.choices[0].message.content
        result = json.loads(gpt_output)
        return result["ood_feedback"], result["explanation"]

    except Exception as e:
        print(f"Error generating OOD with GPT-4: {e}")
        return "OOD feedback generation failed.", "Explanation generation failed."

# Load JSON data
input_json_path = "./output_last_feedback.json"
output_json_path = "./ood_semantic_last_step.json"

with open(input_json_path, 'r') as f:
    data = json.load(f)

# Iterate through the data points and add OOD information
for i, datapoint in enumerate(data):
    original_feedback = datapoint.get("original_feedback", "")
    task = datapoint.get("task", "")
    description = datapoint.get("Description", "")
    oracle = datapoint.get("oracle", "")

    # Generate OOD feedback and explanation using GPT-4
    print(f"Processing datapoint {i+1}/{len(data)}: {datapoint.get('task_name', 'Unnamed Task')}")
    ood_feedback, explanation = generate_ood_with_gpt(description, original_feedback, task, oracle)

    # Add new fields
    datapoint["ood_feedback"] = ood_feedback
    datapoint["ood_type"] = "semantic"
    datapoint["explanation"] = explanation
    print(datapoint)

    # Pause to avoid hitting rate limits
    time.sleep(1)

# Save the updated JSONå
with open(output_json_path, 'w') as f:
    json.dump(data, f, indent=4)

print(f"Updated dataset saved to {output_json_path}")
