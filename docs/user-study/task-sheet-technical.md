# CodeFlow 用户试验任务书（技术背景用户） / CodeFlow User Test Task Sheet (Technical Users)

## 中文版

感谢你参与本次测试。

本次测试主要关注：具有一定技术背景的用户，是否能够较顺利地理解并使用该工具完成代码可视化相关任务。

请在操作过程中尽量说出你在想什么。  
例如：
- “我在找运行按钮”
- “我觉得这里应该是调设置的地方”
- “我不确定这个变量是不是需要单独添加”

请完成以下任务：

### 任务 1
新建一个项目，并输入一段简单 Python 代码运行它。

建议代码：

```python
data = [5, 1, 4, 2, 8]

for i in range(len(data)):
    for j in range(0, len(data) - i - 1):
        if data[j] > data[j + 1]:
            data[j], data[j + 1] = data[j + 1], data[j]
```

### 任务 2
选择一个你想观察的变量，并查看它在不同 step 中的变化。  
请说明你是如何选择这个变量，以及你如何查看它的变化。

### 任务 3
调整一次变量的显示方式，或者修改一次 depth 设置，并观察变化。

### 任务 4
保存当前项目，并重新打开它。

### 自由探索（可选）
如果还有时间，请你自由探索这个工具，并尝试做一件你认为有意义的事情。  
你可以继续修改代码、查看不同 step、调整显示方式，或尝试理解更多内容。  
请继续说出你在想什么，以及你接下来最想做什么。

完成后，请回答几个简短问题：

1. 你觉得哪一步最困惑？
2. 你觉得哪一步最顺手？
3. 如果只能改一个地方，你最希望改哪里？

可选补充问题：

4. 你一开始觉得这个工具是做什么的？
5. 你下次还会愿意使用它吗？
6. 有没有哪个按钮、词语或功能让你一开始理解错了？
7. 你是否理解这里的 view / 显示方式是在控制什么？如果不完全理解，哪里最不清楚？
8. 如果你是开发者，你会愿意继续使用这个工具，或者在它的基础上做扩展吗？为什么？

---

## English Version

Thank you for taking part in this test.

This session focuses on whether users with some technical background can understand and use the tool smoothly for code visualization tasks.

Please try to say out loud what you are thinking while using the system.  
For example:
- “I'm looking for the run button.”
- “I think this might be where I change settings.”
- “I'm not sure whether I need to add this variable separately.”

Please complete the following tasks:

### Task 1
Create a new project, enter a short Python snippet, and run it.

Suggested code:

```python
data = [5, 1, 4, 2, 8]

for i in range(len(data)):
    for j in range(0, len(data) - i - 1):
        if data[j] > data[j + 1]:
            data[j], data[j + 1] = data[j + 1], data[j]
```

### Task 2
Choose one variable that you want to observe, and view how it changes across different steps.  
Please explain how you selected the variable and how you checked its changes.

### Task 3
Change a variable's display style, or modify one depth setting, and observe the result.

### Task 4
Save the current project and reopen it.

### Free Exploration (Optional)
If time allows, please explore the tool freely and try to do one thing that you find meaningful.  
You may continue modifying the code, viewing different steps, changing display settings, or trying to understand more of the content.  
Please continue to say out loud what you are thinking and what you want to do next.

After the tasks are completed, please answer a few short questions:

1. Which step felt the most confusing?
2. Which step felt the easiest or most natural?
3. If you could change only one thing, what would you change?

Optional follow-up questions:

4. What did you think this tool was for at first?
5. Would you be willing to use it again?
6. Was there any button, label, or feature that you misunderstood at first?
7. Do you understand what the view / display mode is controlling here? If not fully, what was unclear?
8. If you were a developer, would you want to keep using this tool or extend it further? Why or why not?
