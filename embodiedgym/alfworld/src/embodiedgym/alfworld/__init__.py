import os

# 取出valid_seen和valid_unseen的所有task的game.tw-pddl文件
ALFWORLD_VALID_SEEN = []
ALFWORLD_VALID_UNSEEN = []

data_path = os.path.join(os.environ["ALFWORLD_DATA"], "json_2.1.1")

valid_unseen_path = os.path.join(data_path, "valid_unseen")
valid_seen_path = os.path.join(data_path, "valid_seen")

# 遍历 valid_unseen 数据集里的所有task
for folder in os.listdir(valid_unseen_path):
    folder_path = os.path.join(valid_unseen_path, folder)
    # 获取子文件夹
    subfolders = [
        sub for sub in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, sub))
    ]
    first_subfolder_path = os.path.join(
        folder_path, subfolders[0]
    )  # 不知道三个trail是干什么的，目前就取第一个trail，数据量已经够多
    ALFWORLD_VALID_UNSEEN.append(first_subfolder_path)

# 遍历 valid_seen 数据集里的所有task
for folder in os.listdir(valid_seen_path):
    folder_path = os.path.join(valid_seen_path, folder)
    subfolders = [
        sub for sub in os.listdir(folder_path) if os.path.isdir(os.path.join(folder_path, sub))
    ]
    ALFWORLD_VALID_SEEN.append(os.path.join(folder_path, subfolders[0]))

print(ALFWORLD_VALID_SEEN)
print(ALFWORLD_VALID_UNSEEN)
