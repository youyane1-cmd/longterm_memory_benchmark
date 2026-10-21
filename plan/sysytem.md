笔记：
"""
1.人物档案：管理人物摘要，调用前需要加载person.json文件转换为profile_data格式
class PersonProfile:
    """持有当前人物档案、结果目录和模型客户端。"""

    def __init__(
        self,
        profile_data: ProfileData,
        save_dir: str | Path,
        llm_client: LLMClient,)
调用：
 profile_data = ProfileData.model_validate(load_data(profile_path))
    profile = PersonProfile(profile_data, output_dir, client)
    summary = profile.save_summary(profile.summarize_profile())
---
```
json转为对象
profile_data = ProfileData.model_validate(load_data(profile_path))
对象转为字典
profile_data.model_dump(mode="json")
"""
model_dump()：得到普通 Python 字典，字段类型尽量保持原样。
model_dump(mode="json")：得到可以直接 json.dumps 的字典，日期、枚举这类类型会先转成 JSON 能表示的值
```
2.人物目标状态规划：管理人物历史目标状态，输入PersonProfile
class TargetState:
    """持有人物状态、累计状态和模型客户端。"""

    def __init__(
        self,
        profile: PersonProfile,
        planning_state: PlanningState,
        llm_client: LLMClient,
        save_dir: str | Path,
    ) -> None:
        self.profile = profile
        self.planning_state = planning_state
        self.llm_client = llm_client
        self.save_dir = Path(save_dir)
设计：
先保存摘要，后续会调用载入摘要的方法
if not profile.summary_path.exists():
        profile.save_summary(profile.summarize_profile())
先看当前版本人物的规划是否存在，不存在就传入空对象，这是只在v0版本才有的情况，因为后续会自动加一。也可换个方法，直接判断是否为v0版本，人物
if not planning_state_file(save_path,ProfileData.person_id,ProfileData.round_id).exists():
    return   PlanningState(person_id="", person_summary="", round_id=profile_data.round_id),
if ProfileData.round_id=="v0":
     return   PlanningState(person_id="", person_summary="", round_id=profile_data.round_id),
else:
输入方式：输入状态规划对象
    @classmethod
        def load_planning_state(
            cls,
            save_dir: str | Path,
            person_id: str,
            round_id: str,
        ) -> PlanningState:
          """按人物和轮次读取累计状态，不需要先创建规划器。"""
        return PlanningState.model_validate(
            load_data(cls.planning_state_file(save_dir, person_id, round_id))
        )
    TargetState.load_planning_state(output_dir, person_id, round_id)


基于人物档案+累计目标状态--更新累计目标状态对象
基于累计目标状态，选定3个domain域的状态链+人物摘要--人物目标状态/人物累计目标状态对象
```
三个装饰器
planner = TargetState(
    profile,
    PlanningState(person_id="", person_summary="", round_id=profile_data.round_id),
    client,
    output_dir,
)
普通方法：必须先创建对象。第一个参数 self 就是这个对象，调用时写括号。
planner.save_round(result)

@property：把该类下的方法当属性调用，不写括号。用的是对象里已经存好的数据。
planner.planning_state_path

@staticmethod：不用创建对象，也没有 self。只使用调用时传入的参数。
TargetState.planning_state_file(output_dir, person_id, round_id)

@classmethod：不用创建对象。第一个参数 cls 是类本身，所以能接着调用这个类的其他方法。
TargetState.load_round(output_dir, person_id, round_id)
里面的 cls.load_planning_state(...) 就是在调用同一个类上的方法。
```
---
