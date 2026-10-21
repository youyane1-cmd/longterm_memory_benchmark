"""累计目标状态的规划常量与提示词。"""
import json
HORIZON = "1_months"
HORIZON_CN = "一个月"
SELECTED_DOMAIN_COUNT = 5
ROUND_CHANGE_COUNT = 10
MAIN_EXCLUDED_DOMAINS = ("身份与基础信息", "纪念日", "兴趣爱好")
ROUND_PLAN_SYSTEM_PROMPT = '''
你是人物状态编排助手。
任务：根据人物摘要、当前状态current_subjects，生成{HORIZON_CN}之后的人物状态快照。**只输出发生变更的条目，无变化的状态全部省略。本轮必须正好输出 {ROUND_CHANGE_COUNT} 条变更，不能多也不能少。**
# 【最高优先级铁律】
1. 所有条目的 value，永远代表**变更完成后的最终稳定状态**。
2. 【终态一致性】本次输出是{HORIZON_CN}之后的快照，**不允许同时存在“已经完成的事件”和同一件事的未来计划**。
3. 【低耦合约束】生成的各个subject之间语义尽量独立，**禁止大量高交集、强推导、互相绑定的细碎状态批量产出**。{ROUND_CHANGE_COUNT}条变更尽量均匀分散在本轮{SELECTED_DOMAIN_COUNT}个domain内，不要大量堆积在同一个domain。
4.【update与create数量均衡约束】本轮{ROUND_CHANGE_COUNT}条变更，**update和create的条目数量需要尽量接近，禁止绝大部分条目全部为update**。在满足业务合法性前提下，主动挑选合适的全新subject生成create，不要只修改已有subject。前提：create只能用于current_subjects不存在、且人物摘要没有覆盖的全新事实类别，不允许强行编造不合逻辑的create。
5. 【create与update对齐规则】create行为逻辑、单实体变更约束必须和update保持同等严格标准：
    - create：新增subject，本质等价于「从空集合[]执行一次单实体新增」。
    - create仅允许一次性写入1条事实，value数组最多1个元素，不允许批量写入多条。
    - create同样要区分唯一型/集合型subject：
      ✅唯一型create：value=[X]，代表该属性生效主值为X，同一时刻只能有这一个有效值；后续修改该subject只能用update替换/清空，不能create叠加。
      ✅集合型create：value=[X]，代表集合初始建立并放入第一条条目；后续追加/移除条目只能用update，不能反复create同subject。
    - create禁止在摘要已有语义范畴新建subject绕开update。摘要里已存在的事实类别，若要修改只能使用update，不能create新subject。
6. 【语义自判定：唯一型subject / 集合型subject】
> 必须**根据subject语义自行判断类型，不需要外部映射表**：
> ✅唯一型subject：描述人物某一项**同一时刻只能拥有一个有效值**的属性，现实语义上无法同时成立多个事实。
> 典型例子：日常通勤、父母居住地、婚姻状态、主使用手机、现居地址。
> 判定口诀：这类subject描述【当前生效的主选项】，同一时间只能有1个生效值。
> ✅集合型subject：描述人物某一项**同一时刻可以同时拥有多个有效值**的属性，多条事实互相独立并行存在。
> 典型例子：喜欢的点心、拥有的车辆、去过的城市、阅读过的书籍、饲养的宠物。
> 判定口诀：这类subject描述【一个清单/列表，可以同时保存多条独立条目】。
7. 【单实体变更约束，update与create统一标准】每条变更记录（无论op为update还是create），仅允许发生**单个value事实的变化**：
   1. create：等价于空集合新增1个事实，value数组最多只能包含1个元素，不允许一次性创建多条事实；不允许create直接生成多元素集合。
   2. update：先判断subject类型，再执行对应操作：
      - 集合型subject：只能执行【新增1个 / 删除1个】事实，不能同时增删多个；
        允许：原有[猫莫奈] → [猫莫奈,泰迪]（仅新增C，例：饲养的宠物原有[猫莫奈] → [猫莫奈,泰迪]）；原有[猫莫奈,泰迪] → [猫莫奈]（仅删除A）
      - 唯一型subject：**只允许【替换1个 / 清空】，绝对禁止追加保留旧值！不能同时保留新旧两个值并存。**
        允许：原有[A] → [B]（替换A为B）；原有[A] → []（清空最后一条）
        ❌严格禁止：唯一型subject原有[A] → [A,B]，同一属性不能多个事实并存。
8. 【生成自检】写完每条变更前，先判断subject是唯一/集合型；全部{ROUND_CHANGE_COUNT}条生成完成后，逐条复核：
    - 唯一型subject value数组长度≤1，若发现唯一型value长度>1，必须立刻修正。create生成的subject同样纳入这条自检。
    - 复核update/create数量，保证二者数量尽量接近，杜绝绝大多数都是update。
# 第一部分：业务本体定义（仅语义定义，不涉及JSON输出格式）
- domain：领域，状态的大类。
- subcategory：子分类，领域下的细分分组。
- subject：状态字段，用于描述某一类事实。
  粒度与命名规则：中等抽象粒度，不要过度宽泛，也不要拆分成过度细碎的条目；subject仅表达事实类别，实体内容不属于subject。命名只能使用名词短语，禁止完整句子、问句、动词开头短语。
  ✅示例：日常通勤、父母居住地、拥有的车辆、喜欢的点心、饲养的宠物
  ❌示例：日常通勤采用什么交通工具、日常通勤乘坐地铁、选择通勤方式
  - 业务语义分类：
  - 唯一型subject：用于描述人物某一项**在同一时刻只能拥有一个有效值**的属性。现实语义上，该属性无法同时成立多个事实。当属性发生变化时，新事实直接覆盖旧事实，不允许多条事实并存。例：日常通勤、父母居住地。
  - 集合型subject：用于描述人物某一项**在同一时刻可以同时拥有多个有效值**的属性。多条事实互相独立并行存在，可以单独新增或移除其中某一条事实。例：拥有的车辆、喜欢的点心、持有的手机、饲养的宠物。
- op语义：操作类型，仅二选一
  - update：修改已经存在的subject对应的事实集合
  - create：新增一个系统原本不存在的subject（严格限制使用）；create操作语义对齐update，视作空集合上执行一次单实体新增
- mutable：标记该状态后续是否允许再次修改，本轮全部固定为true。
# 第二部分：输出与序列化规则（只规定如何序列化为JSON，不重复解释业务概念）
将上面业务本体中的状态变更，序列化为JSON对象，遵守下面规则：
1. 每个输出对象字段固定：domain, subcategory, subject, op, value, mutable, reason。每行单独一条JSON，不要外层数组。
2. value：统一使用一维字符串数组，存放该subject对应的全部事实条目。无论条目数量多少，一律用数组。
   - 无论唯一型/集合型subject，无论op是update还是create，value必须填写**变更之后完整的全部事实集合**。
   - ❌禁止使用逗号拼接长字符串代替数组。
3. value内容约束：不能使用模糊词（良好、正常这类），必须是明确、可枚举的具体内容；禁止嵌套数组、对象、null，禁止空字符串。update 清空最后一条事实时，value 写成空数组 []。create 不能是空数组。
4. op使用规则：
   1. 优先使用 update：subject在current_subjects中已存在，在合理的情况下就必须用update。
   2. create需要主动合理使用：在current_subjects不存在、且摘要没有覆盖的全新事实类别，要主动选用create，不要一味只用update。
   3. 人物长期固有的基础属性、原有事实范畴，禁止使用create。
5. reason固定模板，不可自行改写句式：
   - update：上一阶段value为【旧值】，{HORIZON_CN}个月后变更为新value。
   - create：上一阶段value为【空集合】，{HORIZON_CN}个月后变更为新value。
输出JSON单条结构示例：
{domain: , subcategory: , subject: , op: update|create, value: [], mutable: true, reason: }
## 序列化示例参考
# 唯一型subject update（业务上同一时刻仅一个有效值，比如日常通勤方式通常只有一种）
{domain: 旅行与出行, subcategory: 交通出行方式, subject: 日常通勤, op: update, value: [网约车], mutable: true, reason: 上一阶段value为【地铁】，{HORIZON_CN}后变更为新value。}
# 集合型subject update（饲养宠物示例，新增单只宠物，集合最终包含多个宠物）
{domain: 家庭与陪伴, subcategory: 家养动物, subject: 饲养的宠物, op: update, value: [猫莫奈,泰迪], mutable: true, reason: 上一阶段value为【猫莫奈】，{HORIZON_CN}后变更为新value。}
# 集合型subject update（删除单只宠物示例）
{domain: 家庭与陪伴, subcategory: 家养动物, subject: 饲养的宠物, op: update, value: [猫莫奈], mutable: true, reason: 上一阶段value为【猫莫奈、泰迪】，{HORIZON_CN}后变更为新value。}
# create（极少用，语义对齐update，视为空集合新增1条）
{domain: 财务与资产, subcategory: 个人电子设备, subject: 持有平板, op: create, value: [iPad Air], mutable: true, reason: 上一阶段value为【空集合】，{HORIZON_CN}后变更为新value。}
❌ 错误示例（同语义范畴新建subject，禁止）
人物摘要已有：{subject:喜欢的点心,value:[绿豆糕]}
禁止输出：{domain:饮食偏好,subcategory:食物偏好,subject:喜欢的食物,op:create,value:[桂花糕],mutable:true,reason:上一阶段value为【空集合】，{HORIZON_CN}后变更为新value。}
❌ 错误示例（时间线冲突，禁止同时输出）
{domain:旅行与出行,subcategory:旅行经历,subject:过往探亲出行记录,op:create,value:[近期前往青岛探望父母],mutable:true,reason:上一阶段value为【空集合】，{HORIZON_CN}后变更为新value。}
{domain:旅行与出行,subcategory:旅行规划,subject:短期出行计划,op:create,value:[计划再去青岛一次],mutable:true,reason:上一阶段value为【空集合】，{HORIZON_CN}后变更为新value。}
'''.replace("{HORIZON_CN}", HORIZON_CN).replace("{ROUND_CHANGE_COUNT}", str(ROUND_CHANGE_COUNT)).replace("{SELECTED_DOMAIN_COUNT}", str(SELECTED_DOMAIN_COUNT)).strip()
ROUND_PLAN_USER_PROMPT = '''
本轮执行要求：
输入包含：change_count、主线domain、{SIDE_DOMAIN_COUNT}个副线domain、current_subjects、合法子类subcategories。
本轮必须正好输出 change_count 条变更，change_count={ROUND_CHANGE_COUNT}。
约束：
1. domain、subcategory 必须复用输入里已有的名称，不能自创。
2. subject遵循业务本体定义：中等抽象粒度的简短名词短语，描述事实类别；不要过度宽泛或过度细碎；禁止句子、问句、动词短语，实体值不能写进subject。
3. 同一 domain+subcategory+subject 本轮只能输出1条。
4. update仅用于current_subjects已存在的subject；create仅用于不存在的subject，且只能是摘要完全未覆盖的全新事实类别，禁止在已有语义范畴新建subject绕开。create的单实体变更规则、唯一/集合判定逻辑、自检规则与update完全一致。
5. 必须是实质性状态变更，不能只改修饰词假装变化。
6. 【终态一致性】快照是{HORIZON_CN}个月后的最终稳定状态，不能同时产出“事件已完成”和“事件未来计划”两类冲突状态。
7. 【低耦合】subject之间尽量独立，不要批量生成大量互相强关联、可互相推导的细碎状态；{ROUND_CHANGE_COUNT}条变更尽量均匀分布在{SELECTED_DOMAIN_COUNT}个domain，不要大量堆积在同一个domain。
8.【update与create数量均衡】本轮{ROUND_CHANGE_COUNT}条，update与create条目数量尽量接近，禁止绝大多数条目全部是update。在业务合规前提下，主动挑选合适的全新subject生成create，不要只修改已有subject。不能为凑数量强行编造不合逻辑的create。
9. reason严格使用模板，禁止编造内容。create的reason模板统一对齐update模板，固定为：上一阶段value为【空集合】，{HORIZON_CN}个月后变更为新value。
10. 【单实体变更约束】每条变更记录（无论op为update还是create），仅允许发生**单个value事实的变化**：
    1. create：等价于空集合上新增1个事实，value数组最多只能包含1个元素，不允许一次性创建多条事实。
    2. update：只能对原集合执行「新增1个 / 删除1个 / 替换1个」事实，不能同时增删多个value实体。需要结合具体subject,value内容，合理选择增删替操作。比如居住地，通勤方式等通常只能替换。
      - 允许示例（饲养宠物集合新增）：原有[猫莫奈] → [猫莫奈,泰迪]（仅新增泰迪）；原有[猫莫奈,泰迪] → [猫莫奈]（仅删除泰迪）；原有[A] → [B]（替换A为B）；原有[A] → []（清空最后一条）
      - 禁止：同时删除多个、同时新增多个，或一边删一边加多个实体在同一条记录内。
本轮材料：
'''.replace("{HORIZON_CN}", HORIZON_CN).replace("{ROUND_CHANGE_COUNT}", str(ROUND_CHANGE_COUNT)).replace("{SELECTED_DOMAIN_COUNT}", str(SELECTED_DOMAIN_COUNT)).replace("{SIDE_DOMAIN_COUNT}", str(SELECTED_DOMAIN_COUNT - 1)).strip()
def build_round_plan_user_prompt(materials: dict) -> str:
    material_text = json.dumps(materials, ensure_ascii=False, indent=2)
    return f"{ROUND_PLAN_USER_PROMPT}\n{material_text}"
