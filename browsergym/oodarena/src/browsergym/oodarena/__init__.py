__version__ = "0.0.1"

from browsergym.core.registration import register_task
import json

# 读取 JSON 文件
def read_json_file(file_path):
    with open(file_path, 'r') as file:
        data = json.load(file)
    return data

# 获取 task_id 的范围，并验证连续性
def get_task_id_range_and_check_continuity(data):
    # 提取所有的 task_id
    task_ids = sorted(item["task_id"] for item in data)
    
    # 获取最小和最大 task_id
    min_task_id = min(task_ids)
    max_task_id = max(task_ids)

    # 检查 task_id 是否连续
    is_continuous = all(task_ids[i] == task_ids[i-1] + 1 for i in range(1, len(task_ids)))

    return min_task_id, max_task_id, is_continuous

# 假设 JSON 文件路径
file_path = "./task_data/tasks.json"

# 读取文件数据
data = read_json_file(file_path)

# 获取 task_id 范围和连续性检查
min_id, max_id, continuous = get_task_id_range_and_check_continuity(data)

if not continuous:
    raise ValueError(f"Task IDs are not continuous: {min_id} - {max_id}")

ALL_OODARENA_TASK_IDS = []

for task in data:
    ood_task_type = task["ood_task_type"]
    ood_task_id = task["ood_task_id"]
    
    gym_id = f"oodarena.{ood_task_type}.{ood_task_id}"
    register_task(
        gym_id,
        task.BrowserOODArenaTask,
        task_kwargs={"task_id": ood_task_id}, # TODO
    )
    ALL_OODARENA_TASK_IDS.append(gym_id)