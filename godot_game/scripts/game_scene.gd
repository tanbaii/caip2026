## game_scene.gd — 诈骗拦截大作战（Fraud Interceptor）v4
##
## 快速「分拣」反应游戏：信息卡限时滑入，判断【诈骗→拦截】或【正常→放行】。
##
## 模式（GameManager.game_mode）：
##   · campaign：关卡战役。每关「专属卡池」，清理够 goal 张通关，评 1~3 星并存档解锁。
##   · endless ：无尽模式。撑到防御耗尽冲高分，进入本地最高分榜。
##
## 道具（键盘 Q/W/E；连击每满 6 随机奖励）：火眼金睛 / 时间冻结 / 护盾。
## BOSS 关特殊：① 伪装升级——出现极具迷惑性的「高仿官方」卡；② 连环突袭——每隔几张触发
##             连续 3 张加成（更快更值，全对额外奖励，错一张中断）。
##
## 视觉：每关主题色 + 渐变光晕背景 + 漂浮数据流 + 卡片阴影/圆角 + 滑入 + 浮动得分 +
##       连击进阶特效 + 低防御警示。音效为运行时合成（无需音频素材）。
## 全程不使用字体缺失的 emoji（GameManager.clean 兜底）。
extends Control

const T = GameManager.PixelTheme
const W := 1024.0
const H := 720.0

## 为动态创建的 Label 显式设置字体（CanvasLayer 不继承主题）
func _apply_font(node: Control) -> void:
	GameManager.apply_font(node)

# ── 节点 ──
@onready var bg: ColorRect            = $Background
@onready var hud_title: Label         = $HUD/Title
@onready var hud_wave: Label          = $HUD/Wave
@onready var shields: HBoxContainer   = $HUD/Shields
@onready var combo_lbl: Label         = $HUD/Combo
@onready var score_lbl: Label         = $HUD/Score
@onready var goalbar: ProgressBar     = $GoalBar
@onready var timerbar: ProgressBar    = $TimerBar
@onready var card_layer: Control      = $CardLayer
@onready var powerbar: HBoxContainer  = $PowerBar
@onready var hint: Label              = $Hint
@onready var block_btn: Button        = $Dock/BlockBtn
@onready var pass_btn: Button         = $Dock/PassBtn
@onready var dock: HBoxContainer      = $Dock

@onready var fin: PanelContainer      = $Finish
@onready var fin_title: Label         = $Finish/Margin/VBox/Title
@onready var fin_rating: Label        = $Finish/Margin/VBox/Rating
@onready var fin_score: Label         = $Finish/Margin/VBox/Score
@onready var fin_msg: Label           = $Finish/Margin/VBox/Message
@onready var fin_btns: HBoxContainer   = $Finish/Margin/VBox/Buttons

# ── 关卡 / 模式 ──
var _mode: String = "campaign"
var _stage: Dictionary = {}
var _accent: Color = T.CYA
var _goal: int = 10
var _maxlives: int = 3
var _base_time: float = 5.5
var _is_boss: bool = false

# ── 状态 ──
var _deck: Array = []
var _cur: Dictionary = {}
var _card: Control = null
var _lives: int = 3
var _score: int = 0
var _combo: int = 0
var _best_combo: int = 0
var _answered: int = 0
var _correct: int = 0
var _busy: bool = false
var _over: bool = false
var _timer_tw: Tween

# ── 道具 ──
var _pw: Dictionary = {"eye": 0, "freeze": 0, "shield": 0}
var _pw_btns: Dictionary = {}
var _shield_on: bool = false
var _frozen: bool = false

# ── BOSS 连环突袭 ──
var _chain: int = 0
var _chain_ok: bool = true

# ── 音效（运行时合成） ──
var _players: Array = []
var _pidx: int = 0
var _tones: Dictionary = {}

# ── 顶层特效层（避免被 CardLayer / 背景粒子挡住） ──
var _fx_layer: CanvasLayer = null


# ══════════════════════════════ 信息卡池（专属卡池：按 tag 归类；hard 仅 BOSS/无尽出现） ═══
const CARDS = [
	# ── 冒充公检法 ──
	{"kind":"来电","from":"自称 市公安局","text":"你涉嫌一起洗钱案，需把存款转入「安全账户」配合资金清查，否则上门逮捕。","scam":true,"tag":"冒充公检法","tip":"公检法绝不会电话办案，更没有「安全账户」。挂断并拨 110/96110 核实。"},
	{"kind":"通知","from":"未知号码","text":"您有一份法院传票未签收，案件编号 2026XX，逾期将冻结名下账户，点击查看并配合处理。","scam":true,"tag":"冒充公检法","tip":"法院不会用短信链接送达并要你「配合处理资金」，这是冒充公检法。"},
	{"kind":"来电","from":"自称 通信管理局","text":"您的手机号涉嫌发送大量诈骗短信，2 小时后强制停机，如需申诉请按 9 转接民警。","scam":true,"tag":"冒充公检法","tip":"通信管理局不会来电说你「涉案」，转接「民警」是连环套。"},
	{"kind":"来电","from":"冒充 110","text":"这里是反诈中心，监测到您名下账户异常，现冻结名下资金，请告诉我银行账号以便核查。","scam":true,"tag":"冒充公检法","tip":"真反诈中心绝不会索要你的银行账号，挂断后自行拨打 96110 核实。"},
	# ── 刷单返利 ──
	{"kind":"短信","from":"兼职招聘","text":"足不出户日结 300+，先垫付后秒返本金加佣金，加微信领任务。","scam":true,"tag":"刷单返利","tip":"凡「先垫付后返利」的兼职都是诈骗，前期小返现只为骗你做大额。"},
	{"kind":"短信","from":"点赞任务群","text":"点赞关注做任务，30 秒一单佣金 5 元，做满 20 单解锁高佣，押金可退。","scam":true,"tag":"刷单返利","tip":"刷单本身违法，押金可退是诱饵，做大单后就提不了现。"},
	# ── 冒充客服理赔 ──
	{"kind":"来电","from":"自称 网店客服","text":"您买的奶粉质检不合格，为您办理三倍理赔，请共享屏幕按我说的操作。","scam":true,"tag":"冒充客服理赔","tip":"退款只在原平台操作；要求屏幕共享、念验证码、去借贷转账的都是诈骗。"},
	{"kind":"短信","from":"自称 平台专员","text":"您的订单触发异常理赔，加专员微信领取 588 元补偿，逾期作废。","scam":true,"tag":"冒充客服理赔","tip":"主动「异常理赔」让你加私人微信的，是冒充客服诈骗。"},
	{"kind":"来电","from":"自称 快递客服","text":"您的快递丢失，我们将双倍赔付 200 元，请按语音提示输入银行卡号和密码完成理赔。","scam":true,"tag":"冒充客服理赔","tip":"快递理赔无需银行卡密码和语音操作，直接挂断后联系官方核实。"},
	# ── 中奖免费送 ──
	{"kind":"通知","from":"未知号码","text":"恭喜您被抽中免费送扫地机器人！仅需支付 99 元运费，点 t.cn/xxx 领取。","scam":true,"tag":"中奖免费送","tip":"领奖前要先交钱的都是诈骗，天上不会掉馅饼。"},
	{"kind":"短信","from":"周年庆活动","text":"您手机号被抽为幸运用户，免费领黄金吊坠，仅付保价费 68 元。","scam":true,"tag":"中奖免费送","tip":"莫名「中奖」还要先付费的，都是骗局。"},
	# ── 虚假贷款 ──
	{"kind":"短信","from":"贷款平台","text":"无抵押当天放款 5 万，因银行卡号填错被冻结，需缴解冻金激活。","scam":true,"tag":"虚假贷款","tip":"正规贷款放款前绝不收费，先交解冻金/保证金的都是骗局。"},
	{"kind":"短信","from":"某金融","text":"您已预审通过 20 万额度，下款前需购买一份信用保证保险 1980 元。","scam":true,"tag":"虚假贷款","tip":"放款前以「保证保险/会员费」收费的都是虚假贷款诈骗。"},
	# ── 机票退改签 ──
	{"kind":"短信","from":"95xxx","text":"您预订的航班已取消，可领 300 元延误补偿，请按短信链接操作。","scam":true,"tag":"机票退改签","tip":"退改签只走航司官方渠道，不点陌生链接、不填验证码。"},
	{"kind":"来电","from":"自称 航空客服","text":"您的航班因天气取消，致电客服办理改签将退还差价 420 元，请提供银行卡。","scam":true,"tag":"机票退改签","tip":"索要银行卡/验证码办「退差价」的是诈骗，挂断拨航司官方电话。"},
	# ── 钓鱼短信 ──
	{"kind":"短信","from":"积分中心","text":"您的积分即将清零，点击 http://hd-jf.cn 兑换现金等好礼。","scam":true,"tag":"钓鱼短信","tip":"官方短信不会带不明链接索要密码/验证码，链接域名也对不上。"},
	{"kind":"短信","from":"ETC 中心","text":"您的 ETC 已失效，请点击 etc-rz.cn 重新认证，逾期将无法通行。","scam":true,"tag":"钓鱼短信","tip":"ETC/银行卡「失效认证」短信链接是钓鱼，去官方 App 或网点办理。"},
	# ── 冒充客服扣费 ──
	{"kind":"来电","from":"自称 客服","text":"您的百万保障将到期，每月自动扣费 800 元，需立即取消并验证账户。","scam":true,"tag":"冒充客服扣费","tip":"莫名「会员/保障到期扣费」是恐吓话术，不点链接、不共享屏幕。"},
	{"kind":"短信","from":"自称 视频客服","text":"您开通的会员连续包年将扣费 348 元，如需取消请按提示操作并验证。","scam":true,"tag":"冒充客服扣费","tip":"取消扣费在原 App 内操作，按陌生「提示验证」就是诈骗。"},
	{"kind":"来电","from":"自称 抖音客服","text":"您开通了直播会员，每月将扣 500 元，请问要取消吗？先验证一下您名下银行卡信息。","scam":true,"tag":"冒充客服扣费","tip":"这类「误开会员需验证银行卡」是诈骗变种，不要配合操作。"},
	# ── 快递理赔 ──
	{"kind":"短信","from":"快递客服","text":"您的快递在运输中丢失，现为您双倍赔付，请扫描二维码领取赔款。","scam":true,"tag":"快递理赔","tip":"主动高额理赔 + 扫码/填银行卡，是典型诈骗，去官方 App 核实。"},
	{"kind":"短信","from":"自称 物流","text":"您的包裹在分拣中损毁，扫码登记银行卡办理三倍赔付，今日有效。","scam":true,"tag":"快递理赔","tip":"理赔不需要你的银行卡和密码，扫码填卡就是骗局。"},
	# ── 注销校园贷 ──
	{"kind":"来电","from":"自称 金融客服","text":"您的校园贷账户未注销将影响征信，请配合把网贷额度提现转入对冲账户清零。","scam":true,"tag":"注销校园贷","tip":"没用过的校园贷无需注销；让你借款转给他人的一律是诈骗。"},
	{"kind":"来电","from":"自称 监管客服","text":"学生专属账户需按监管注销，否则上报征信影响考公，请联系客服操作。","scam":true,"tag":"注销校园贷","tip":"征信不会因「不注销学生账户」受损，这是注销校园贷骗局。"},
	# ── 冒充老师收费 ──
	{"kind":"群消息","from":"群内 自称班主任","text":"各位家长，本学期资料费 380 元，请扫码统一缴纳，缴费后接龙确认。","scam":true,"tag":"冒充老师收费","tip":"群里突然扫码收费要警惕，先电话联系老师本人核实。"},
	{"kind":"群消息","from":"群内 自称老师","text":"紧急征订教辅 256 元，扫码后回复孩子姓名，名额有限速缴。","scam":true,"tag":"冒充老师收费","tip":"催促扫码缴费 + 头像仿冒老师，是混群冒充诈骗。"},
	# ── 冒充熟人 ──
	{"kind":"好友","from":"自称 老同学","text":"我手机进水换了新号，你先帮我给这个账户转 8000 应急，回头还你。","scam":true,"tag":"冒充熟人","tip":"凡换号 + 要转账，务必电话或当面核实本人。"},
	{"kind":"好友","from":"陌生号","text":"在吗？猜猜我是谁～我换号了，正好有件急事想麻烦你周转一下。","scam":true,"tag":"冒充熟人","tip":"「猜猜我是谁 + 借钱」是经典冒充熟人套路，先核实身份。"},
	# ── 冒充领导 ──
	{"kind":"好友","from":"自称 领导","text":"加我新号，有笔款急着打给客户，你先帮我转一下，回公司报销。","scam":true,"tag":"冒充领导","tip":"对「换号、在开会、不能通话、催转账」的组合高度警惕，当面核实。"},
	{"kind":"好友","from":"自称 老板","text":"明天来我办公室一趟，先别声张；手头紧，先帮单位垫付一笔货款。","scam":true,"tag":"冒充领导","tip":"以「保密 + 垫付」绕开财务流程的转账要求，基本是冒充领导。"},
	# ── 虚假投资 ──
	{"kind":"短信","from":"投资群","text":"跟着导师内部计划稳赚不赔，今日布局名额仅剩 3 个，私聊领取。","scam":true,"tag":"虚假投资","tip":"承诺稳赚不赔、内部消息的都是诈骗，盈利截图极易伪造。"},
	{"kind":"短信","from":"VIP 直播间","text":"加入直播间老师带单，今天进场明天翻倍，错过再等一年。","scam":true,"tag":"虚假投资","tip":"「带单翻倍」是虚假投资平台套路，后台操纵涨跌、提现即失联。"},
	# ── 杀猪盘 ──
	{"kind":"好友","from":"网恋对象","text":"我有内部理财渠道，咱俩一起投攒钱买房，先投 1 万试试水。","scam":true,"tag":"杀猪盘","tip":"网恋 + 荐投资 = 杀猪盘，平台由骗子操控，加仓后无法提现。"},
	{"kind":"好友","from":"网恋对象","text":"宝，我表哥在平台有内部漏洞，跟着投稳赚，咱们攒钱去领证。","scam":true,"tag":"杀猪盘","tip":"以感情诱导你投资「内部漏洞」的，是杀猪盘，钱进去就拿不回。"},
	# ── 解冻民族资产 ──
	{"kind":"群消息","from":"民族大业群","text":"缴 99 元会费即可解冻领取 380 万民族资产补助，名额有限！","scam":true,"tag":"解冻民族资产","tip":"国家从无此类项目，交小钱领巨款必是骗局，常针对老人。"},
	{"kind":"群消息","from":"扶贫专项群","text":"注册会员交 188 元工本费，可领取 50 万精准帮扶金，速度报名。","scam":true,"tag":"解冻民族资产","tip":"伪造的「国家专项/帮扶金」收费骗局，告诉家里老人别信。"},

	# ── 正常信息（放行） ──
	{"kind":"短信","from":"中国工商银行","text":"您尾号 1234 账户 10月21日 12:30 支出 500.00 元，余额 3200.00 元。","scam":false,"tag":"正常银行通知","tip":"银行的消费提醒只告知交易，不索要密码/验证码，属正常通知。"},
	{"kind":"短信","from":"中国建设银行","text":"您尾号 8866 卡 11月1日 09:12 工资入账 6800.00 元。","scam":false,"tag":"正常银行通知","tip":"到账提醒、无链接无索要信息，属正常。"},
	{"kind":"短信","from":"验证码","text":"您的验证码是 728193，10 分钟内有效，请勿告诉他人。","scam":false,"tag":"正常验证码","tip":"这条通知本身正常——记住验证码任何人都不能给，包括「客服」。"},
	{"kind":"短信","from":"微信","text":"您正在登录新设备，验证码 419872，5 分钟内有效，请勿泄露。","scam":false,"tag":"正常验证码","tip":"登录验证码属正常；但若非本人操作，要警惕账号被盗。"},
	{"kind":"通知","from":"菜鸟驿站","text":"您的快递已到，取件码 8-2-1023，请凭码到驿站取件。","scam":false,"tag":"正常物流","tip":"取件码用于线下取件、不涉及转账，属正常通知。"},
	{"kind":"通知","from":"顺丰速运","text":"您的快件已由本人签收，如非本人请联系 95338。","scam":false,"tag":"正常物流","tip":"签收通知、官方客服号，属正常。"},
	{"kind":"短信","from":"中国移动","text":"您本月已用流量 18.2GB，剩余 6.8GB，详情请登录手机营业厅查询。","scam":false,"tag":"正常运营商","tip":"如实告知用量、引导你去官方营业厅，没有诱导转账，属正常。"},
	{"kind":"短信","from":"中国电信","text":"您的话费余额为 23.50 元，为避免停机请及时充值。","scam":false,"tag":"正常运营商","tip":"余额提醒、走官方充值，属正常。"},
	{"kind":"好友","from":"妈妈","text":"周末回家吃饭吗？给你买了爱吃的水果~","scam":false,"tag":"正常家人消息","tip":"日常关心、不涉及金钱与链接，放行即可。"},
	{"kind":"好友","from":"爸爸","text":"天冷了记得加衣服，钱够花吗？不够跟家里说。","scam":false,"tag":"正常家人消息","tip":"家人关心、未涉及陌生账户转账，属正常。"},
	{"kind":"通知","from":"12306","text":"您购买的 G1234 次列车已支付成功，10月25日 08:00 北京南站检票。","scam":false,"tag":"正常购票","tip":"官方出行通知、信息与你的购票一致，属正常。"},
	{"kind":"短信","from":"招商银行","text":"您的信用卡账单已出，应还 2350 元，还款日 11月5日，详情见手机银行。","scam":false,"tag":"正常账单","tip":"账单提醒引导你用官方手机银行，未索要密码，属正常。"},
	{"kind":"群消息","from":"公司同事群","text":"明天 10 点会议室开周会，记得带上项目周报。","scam":false,"tag":"正常工作消息","tip":"工作安排、无收费无链接，放行即可。"},
	{"kind":"群消息","from":"项目群","text":"今天的需求文档我已上传到共享盘，大家有空过一下。","scam":false,"tag":"正常工作消息","tip":"内部协作通知、无转账无链接，属正常。"},
	{"kind":"通知","from":"美团","text":"您的订单已送达，请及时取餐，祝您用餐愉快！","scam":false,"tag":"正常外卖","tip":"配送状态通知，不涉及转账，属正常。"},
	{"kind":"通知","from":"学校","text":"家长会定于本周五下午 3 点在各班教室举行，请准时参加（本次不收取任何费用）。","scam":false,"tag":"正常校园通知","tip":"明确不收费、走正式通知，属正常；若群里突然扫码缴费才要警惕。"},
	{"kind":"通知","from":"国家政务服务平台","text":"您申请的电子社保卡已签发，可在 App 中查看。","scam":false,"tag":"正常政务","tip":"官方政务 App 内查看、不索要银行卡密码，属正常。"},
	{"kind":"通知","from":"XX 医院","text":"您预约的内科门诊为明日 9:30，请提前 15 分钟取号。","scam":false,"tag":"正常医疗","tip":"就诊预约提醒、无转账，属正常。"},
	{"kind":"短信","from":"国家反诈中心","text":"温馨提示：陌生链接不点击，转账汇款多核实，遇可疑情况拨打 96110。","scam":false,"tag":"官方反诈提示","tip":"这是官方反诈宣传，放行——并记住这句口诀。"},
	{"kind":"通知","from":"已安装的购物 App","text":"您收藏的商品降价了，打开 App 查看（来自你订阅的降价提醒）。","scam":false,"tag":"正常 App 推送","tip":"来自你已安装并订阅的 App、在 App 内查看，不要求转账，属正常。"},

	# ── 正常来电（供"来电惊魂"等关卡使用）──
	{"kind":"来电","from":"快递员","text":"您好，您的快递到了，我现在在小区门口，麻烦下来取一下。","scam":false,"tag":"正常快递","tip":"快递员来电通知取件，不涉及转账和个人信息，属正常。"},
	{"kind":"来电","from":"同事","text":"喂，明天上午 10 点的项目会改到下午 3 点了，记得带上方案。","scam":false,"tag":"正常工作消息","tip":"同事电话通知会议变更，无任何转账要求，放行即可。"},
	{"kind":"来电","from":"妈妈","text":"孩子，这周末你爸生日，记得回来吃饭啊，路上注意安全。","scam":false,"tag":"正常家人消息","tip":"家人来电关心、不涉及转账，属正常。"},
	{"kind":"来电","from":"招商银行","text":"您好，您的信用卡本月账单 2350 元已生成，还款日 11 月 5 日，请登录手机银行查看详情。","scam":false,"tag":"正常账单","tip":"银行客服来电只会提醒还款，不会索要密码或让你转账，属正常。"},

	# ── BOSS / 无尽 专属：伪装升级（极具迷惑性，hard=true） ──
	{"kind":"短信","from":"95588","text":"【工商银行】检测到您账户异地登录风险，为保障资金安全请点击 icbc-safe.cn 验证身份。","scam":true,"hard":true,"tag":"钓鱼短信","tip":"高仿官方号 + 安全验证链接仍是钓鱼——银行不会发链接让你「验证身份」。"},
	{"kind":"通知","from":"顺丰速运","text":"您有一件到付包裹待签收，运费 39 元，请点击链接确认收货并支付。","scam":true,"hard":true,"tag":"快递理赔","tip":"陌生「到付/确认收货支付」链接是诈骗，没网购就别点，核对订单来源。"},
	{"kind":"来电","from":"自称 反诈中心","text":"我是反诈中心民警，您的卡涉案，现指导您把资金转入「核查账户」以解除冻结。","scam":true,"hard":true,"tag":"冒充公检法","tip":"连「反诈中心」都能被冒充！真反诈绝不会要你转账，挂断拨 96110 核实。"},
	{"kind":"短信","from":"10086","text":"【中国移动】您参与的话费充值已到账 50 元，感谢您的使用。","scam":false,"hard":true,"tag":"正常运营商","tip":"官方端口、到账告知、无链接无索要——别被「充值」字眼吓到误拦。"},
	{"kind":"短信","from":"12381","text":"【涉诈预警】您近期接听的某号码涉嫌诈骗，请提高警惕，切勿向陌生人转账。","scam":false,"hard":true,"tag":"官方反诈提示","tip":"12381 是工信部涉诈预警，收到说明你接触了高风险号码——这是保护你，放行。"},
]


func _ready() -> void:
	_setup()
	_init_audio()
	_style()
	_build_bg()
	_ensure_fx_layer()
	_build_powerbar()
	block_btn.pressed.connect(_on_block)
	pass_btn.pressed.connect(_on_pass)
	fin.hide()
	_reset()
	await _intro()
	if not is_inside_tree(): return
	_draw_card()


func _setup() -> void:
	_mode = GameManager.game_mode
	if _mode == "campaign":
		var i := clampi(GameManager.game_stage, 0, GameManager.STAGES.size() - 1)
		GameManager.game_stage = i
		_stage = GameManager.STAGES[i]
		_accent = GameManager.theme_color(str(_stage.get("theme", "cya")))
		_maxlives = int(_stage.get("lives", 3))
		_goal = int(_stage.get("goal", 10))
		_base_time = float(_stage.get("time", 5.0))
		_is_boss = i == GameManager.STAGES.size() - 1
	else:
		_stage = {}
		_accent = T.CYA
		_maxlives = 3
		_goal = 0
		_base_time = 5.6
		_is_boss = false


# ══════════════════════════════ 音效（运行时合成 WAV，无需素材） ══════════════════════════════

func _init_audio() -> void:
	for _i in 6:
		var p := AudioStreamPlayer.new()
		add_child(p)
		_players.append(p)
	_tones = {
		"correct": _tone(880.0, 0.12, 0.22, "sine"),
		"wrong":   _tone(150.0, 0.22, 0.28, "square"),
		"combo":   _tone(1240.0, 0.12, 0.22, "sine"),
		"power":   _tone(700.0, 0.12, 0.20, "sine"),
		"win":     _tone(990.0, 0.30, 0.24, "sine"),
	}

func _tone(freq: float, dur: float, vol: float, kind: String) -> AudioStreamWAV:
	var rate := 22050
	var n := int(rate * dur)
	var bytes := PackedByteArray()
	bytes.resize(n * 2)
	for i in n:
		var t := float(i) / float(rate)
		var env := 1.0 - float(i) / float(n)          # 线性衰减
		var s := sin(TAU * freq * t)
		if kind == "square":
			s = 1.0 if s >= 0.0 else -1.0
		var v := int(clampf(s * env * vol, -1.0, 1.0) * 32767.0)
		bytes.encode_s16(i * 2, v)
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = rate
	wav.stereo = false
	wav.data = bytes
	return wav

func _sfx(name: String) -> void:
	if _players.is_empty() or not _tones.has(name):
		return
	var p: AudioStreamPlayer = _players[_pidx]
	_pidx = (_pidx + 1) % _players.size()
	p.stream = _tones[name]
	p.play()


# ══════════════════════════════ 样式 / 背景 ══════════════════════════════

func _style() -> void:
	bg.color = T.BG0
	hud_title.text = _stage_title()
	hud_title.add_theme_color_override("font_color", _accent)
	hud_wave.add_theme_color_override("font_color", T.CYA)
	score_lbl.add_theme_color_override("font_color", T.YEL)
	combo_lbl.add_theme_color_override("font_color", T.ORG)
	hint.add_theme_color_override("font_color", T.TX2)
	goalbar.add_theme_stylebox_override("background", T.box(T.BG1, T.BOR, 1))
	var gf := StyleBoxFlat.new(); gf.bg_color = _accent; gf.set_corner_radius_all(3)
	goalbar.add_theme_stylebox_override("fill", gf)
	timerbar.add_theme_stylebox_override("background", T.box(T.BG1, T.BOR, 1))
	var tf := StyleBoxFlat.new(); tf.bg_color = _accent; tf.set_corner_radius_all(3)
	timerbar.add_theme_stylebox_override("fill", tf)
	block_btn.text = "拦截\n（诈骗）"
	pass_btn.text = "放行\n（安全）"
	_btn(block_btn, T.MAG)
	_btn(pass_btn, T.GRE)
	var fbox := T.box(T.BG2, _accent, 2)
	fbox.set_corner_radius_all(12)
	fbox.shadow_color = Color(0, 0, 0, 0.45); fbox.shadow_size = 14
	fbox.content_margin_left = 6; fbox.content_margin_right = 6
	fin.add_theme_stylebox_override("panel", fbox)


func _stage_title() -> String:
	if _mode == "endless":
		return "无尽模式"
	return "第 %d 关 · %s" % [GameManager.game_stage + 1, GameManager.clean(str(_stage.get("name", "")))]


func _btn(b: Button, c: Color) -> void:
	var n := T.box(c.darkened(0.58), c, 2); n.set_corner_radius_all(10)
	var h := T.box(c.darkened(0.42), c.lightened(0.2), 2); h.set_corner_radius_all(10)
	var p := T.box(c.darkened(0.66), c, 2); p.set_corner_radius_all(10)
	var d := T.box(T.BG1, T.BOR, 1); d.set_corner_radius_all(10)
	b.add_theme_stylebox_override("normal", n)
	b.add_theme_stylebox_override("hover", h)
	b.add_theme_stylebox_override("pressed", p)
	b.add_theme_stylebox_override("disabled", d)
	b.add_theme_color_override("font_color", c.lightened(0.35))
	b.add_theme_color_override("font_hover_color", T.TX1)
	b.add_theme_color_override("font_pressed_color", T.TX1)
	b.add_theme_color_override("font_disabled_color", T.TX3)
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND


## 渐变光晕背景 + 漂浮数据流（每关主题色）
func _build_bg() -> void:
	bg.color = T.BG0
	var grad := Gradient.new()
	grad.set_color(0, T.BG0.lerp(_accent, 0.20))
	grad.set_color(1, T.BG0)
	var tex := GradientTexture2D.new()
	tex.gradient = grad
	tex.fill = GradientTexture2D.FILL_RADIAL
	tex.fill_from = Vector2(0.5, 0.32)
	tex.fill_to = Vector2(1.05, 1.05)
	tex.width = 256
	tex.height = 256
	var tr := TextureRect.new()
	tr.texture = tex
	tr.stretch_mode = TextureRect.STRETCH_SCALE
	tr.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	tr.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(tr)
	move_child(tr, 1)
	for _i in 16:
		var col := ColorRect.new()
		col.color = Color(_accent.r, _accent.g, _accent.b, randf_range(0.03, 0.07))
		col.size = Vector2(randf_range(1.0, 2.5), randf_range(40.0, 130.0))
		col.position = Vector2(randf_range(0.0, W), randf_range(-200.0, H))
		col.mouse_filter = Control.MOUSE_FILTER_IGNORE
		add_child(col)
		move_child(col, 2)
		var dur := randf_range(4.0, 8.0)
		var tw := create_tween().set_loops()
		tw.tween_property(col, "position:y", H + 60.0, dur).from(-160.0)


# ══════════════════════════════ 道具栏 ══════════════════════════════

func _pw_name(key: String) -> String:
	match key:
		"eye": return "火眼金睛"
		"freeze": return "时间冻结"
		"shield": return "护盾"
		_: return key

func _pw_color(key: String) -> Color:
	match key:
		"eye": return T.CYA
		"freeze": return T.YEL
		"shield": return T.GRE
		_: return T.CYA

func _build_powerbar() -> void:
	for c in powerbar.get_children(): c.queue_free()
	_pw_btns.clear()
	for key in ["eye", "freeze", "shield"]:
		var c: Color = _pw_color(key)
		var b := Button.new()
		b.custom_minimum_size = Vector2(0, 34)
		b.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		var n := T.box(c.darkened(0.62), c, 1); n.set_corner_radius_all(8)
		var h := T.box(c.darkened(0.45), c.lightened(0.2), 1); h.set_corner_radius_all(8)
		var pr := T.box(c.darkened(0.68), c, 1); pr.set_corner_radius_all(8)
		var d := T.box(T.BG1, T.BOR, 1); d.set_corner_radius_all(8)
		b.add_theme_stylebox_override("normal", n)
		b.add_theme_stylebox_override("hover", h)
		b.add_theme_stylebox_override("pressed", pr)
		b.add_theme_stylebox_override("disabled", d)
		b.add_theme_color_override("font_color", c.lightened(0.3))
		b.add_theme_color_override("font_disabled_color", T.TX3)
		b.add_theme_font_size_override("font_size", 13)
		_apply_font(b)
		b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		b.pressed.connect(_use_power.bind(key))
		powerbar.add_child(b)
		_pw_btns[key] = b

func _update_powerbar() -> void:
	for key in _pw_btns:
		var b: Button = _pw_btns[key]
		b.text = "%s x%d" % [_pw_name(key), int(_pw.get(key, 0))]
		b.disabled = _over or int(_pw.get(key, 0)) <= 0

func _use_power(key: String) -> void:
	if _busy or _over or _cur.is_empty(): return
	if int(_pw.get(key, 0)) <= 0: return
	_pw[key] = int(_pw[key]) - 1
	_sfx("power")
	match key:
		"eye":
			var is_scam := bool(_cur.get("scam", false))
			var btn: Button = block_btn if is_scam else pass_btn
			_pulse_button(btn)
			_popup("火眼金睛：建议" + ("拦截" if is_scam else "放行"), T.CYA)
		"freeze":
			_frozen = true
			_stop_timer()
			timerbar.value = 1.0
			_popup("时间冻结", T.YEL)
		"shield":
			_shield_on = true
			_popup("护盾就绪", T.GRE)
	_update_powerbar()

func _pulse_button(b: Button) -> void:
	var tw := create_tween()
	tw.tween_property(b, "modulate", Color(1.5, 1.5, 1.5), 0.12)
	tw.tween_property(b, "modulate", Color.WHITE, 0.35)


# ══════════════════════════════ 回合控制 ══════════════════════════════

func _reset() -> void:
	_lives = _maxlives
	_score = 0; _combo = 0; _best_combo = 0
	_answered = 0; _correct = 0; _busy = false; _over = false
	_shield_on = false; _frozen = false
	_chain = 0; _chain_ok = true
	_pw = {"eye": 2, "freeze": 2, "shield": 1} if _mode == "campaign" else {"eye": 1, "freeze": 2, "shield": 1}
	_build_deck()
	_set_shields(_lives)
	_update_hud()
	_update_goal()
	_update_powerbar()


## 专属卡池：该关涉及类别的诈骗 + 适量正常信息；伪装升级卡(hard)仅 BOSS/无尽出现
## 战役模式自动排除已在前置关卡出现过的题目 + 按关卡渠道(kinds)过滤
func _build_deck() -> void:
	var cats: Array = _stage.get("cats", []) if _mode == "campaign" else []
	var kinds: Array = _stage.get("kinds", []) if _mode == "campaign" else []
	var allow_hard := _is_boss or _mode == "endless"
	var scam_pool: Array = []
	var legit_pool: Array = []
	var used: PackedStringArray = GameManager.campaign_used_texts if _mode == "campaign" else []
	for c in CARDS:
		if bool(c.get("hard", false)) and not allow_hard:
			continue
		if _mode == "campaign" and used.has(str(c.get("text", ""))):
			continue
		if _mode == "campaign" and not kinds.is_empty() and not kinds.has(str(c.get("kind", ""))):
			continue
		if bool(c.get("scam", false)):
			if cats.is_empty() or cats.has(str(c.get("tag", ""))):
				scam_pool.append(c)
		else:
			legit_pool.append(c)
	# 类别过滤后若无诈骗卡，回退到全量诈骗池（但排除已用的 + 保留渠道过滤），避免空 deck
	if scam_pool.is_empty():
		for c in CARDS:
			if bool(c.get("hard", false)) and not allow_hard:
				continue
			if _mode == "campaign" and used.has(str(c.get("text", ""))):
				continue
			if _mode == "campaign" and not kinds.is_empty() and not kinds.has(str(c.get("kind", ""))):
				continue
			if bool(c.get("scam", false)):
				scam_pool.append(c)
	# 再次兜底：若已用卡过多导致全量也空，取消去重
	if scam_pool.is_empty():
		for c in CARDS:
			if bool(c.get("hard", false)) and not allow_hard:
				continue
			if bool(c.get("scam", false)):
				scam_pool.append(c)
	# 最后一层兜底：若 legit 池也被渠道/去重清空，回退到无过滤
	if legit_pool.is_empty() and _mode == "campaign":
		for c in CARDS:
			if bool(c.get("hard", false)) and not allow_hard:
				continue
			if not bool(c.get("scam", false)):
				legit_pool.append(c)
	legit_pool.shuffle()
	var keep: int = min(legit_pool.size(), maxi(scam_pool.size() + 4, 4))
	var pool: Array = scam_pool + legit_pool.slice(0, keep)
	pool.shuffle()
	_deck = pool


## 关前提示横幅
func _intro() -> void:
	var p := PanelContainer.new()
	p.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var sb := T.box(T.BG2, _accent, 2); sb.set_corner_radius_all(10)
	p.add_theme_stylebox_override("panel", sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var m := MarginContainer.new()
	m.add_theme_constant_override("margin_left", 24)
	m.add_theme_constant_override("margin_right", 24)
	p.add_child(m)
	var v := VBoxContainer.new()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_theme_constant_override("separation", 14)
	m.add_child(v)
	var t := Label.new()
	t.text = _stage_title()
	t.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	t.add_theme_color_override("font_color", _accent)
	t.add_theme_font_size_override("font_size", 30)
	_apply_font(t)
	v.add_child(t)
	var s := Label.new()
	s.text = "撑到防御耗尽，挑战最高分！" if _mode == "endless" else GameManager.clean(str(_stage.get("intro", "")))
	s.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	s.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	s.add_theme_color_override("font_color", T.TX2)
	s.add_theme_font_size_override("font_size", 15)
	_apply_font(s)
	v.add_child(s)
	var g := Label.new()
	if _is_boss:
		g.text = "BOSS：警惕「高仿官方」卡，注意「连环突袭」加成！"
		g.add_theme_color_override("font_color", T.MAG)
	else:
		g.text = ("目标：清理 %d 条可疑信息" % _goal) if _mode == "campaign" else "准备好了吗？"
		g.add_theme_color_override("font_color", T.TX3)
	g.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	g.add_theme_font_size_override("font_size", 13)
	_apply_font(g)
	v.add_child(g)
	card_layer.add_child(p)
	p.modulate.a = 0.0
	var tw := create_tween()
	tw.tween_property(p, "modulate:a", 1.0, 0.25)
	tw.tween_interval(1.3)
	tw.tween_property(p, "modulate:a", 0.0, 0.25)
	await tw.finished
	if is_instance_valid(p): p.queue_free()


func _draw_card() -> void:
	_clear_layer()
	if _deck.is_empty():
		_build_deck()
	if _deck.is_empty():
		push_error("诈骗拦截：当前关卡卡池为空，无法出题")
		return
	_frozen = false
	# BOSS 连环突袭：每隔 5 张触发一次连续 3 张加成
	if _is_boss and _chain <= 0 and _answered > 0 and _answered % 5 == 0:
		_chain = 3
		_chain_ok = true
		_popup("连环突袭！连续 3 张加成", T.MAG)
		_flash_screen(T.MAG)
		_sfx("combo")
	_cur = _deck.pop_back()
	# 战役模式记录已用卡牌，确保关卡间不重复
	if _mode == "campaign":
		var t := str(_cur.get("text", ""))
		if not GameManager.campaign_used_texts.has(t):
			GameManager.campaign_used_texts.append(t)
	_card = _make_card(_cur)
	card_layer.add_child(_card)
	block_btn.disabled = false
	pass_btn.disabled = false
	# 等一帧完成 CardLayer 布局后再播放入场，避免全屏锚点卡尺寸为 0 或透明卡住
	call_deferred("_run_card_entrance")
	_start_timer()


## 立即清空题目层（queue_free 会延迟到帧末，同帧 add_child 会导致旧卡遮挡新题）
func _clear_layer() -> void:
	for c in card_layer.get_children():
		card_layer.remove_child(c)
		c.queue_free()
	_card = null


func _card_panel() -> Control:
	if _card == null or not is_instance_valid(_card):
		return null
	return _card.get_node_or_null("CardPanel") as Control


func _run_card_entrance() -> void:
	if _over or not is_instance_valid(_card):
		return
	var panel := _card_panel()
	if panel == null:
		return
	panel.modulate.a = 0.0
	panel.offset_top = 26.0
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(panel, "modulate:a", 1.0, 0.2)
	tw.parallel().tween_property(panel, "offset_top", 0.0, 0.25)
	tw.finished.connect(func():
		if is_instance_valid(panel):
			panel.modulate.a = 1.0
			panel.offset_top = 0.0
	)


# ══════════════════════════════ 输入 / 判定 ══════════════════════════════

func _on_block() -> void: _resolve(1)
func _on_pass() -> void:  _resolve(0)

func _unhandled_input(event: InputEvent) -> void:
	if _over: return
	if not (event is InputEventKey): return
	var k := event as InputEventKey
	if not k.pressed or k.echo: return
	match k.keycode:
		KEY_LEFT, KEY_J, KEY_1:
			_resolve(1)
		KEY_RIGHT, KEY_K, KEY_2:
			_resolve(0)
		KEY_Q:
			_use_power("eye")
		KEY_W:
			_use_power("freeze")
		KEY_E:
			_use_power("shield")


## choice: 1=拦截(玩家判定为诈骗)  0=放行(判定为正常)  -1=超时
func _resolve(choice: int) -> void:
	if _busy or _over or _cur.is_empty(): return
	_busy = true
	_stop_timer()
	block_btn.disabled = true
	pass_btn.disabled = true

	var is_scam := bool(_cur.get("scam", false))
	var correct := (choice == 1 and is_scam) or (choice == 0 and not is_scam)
	var missed := choice == -1
	_answered += 1

	var gained := 0
	if correct:
		_correct += 1
		_combo += 1
		_best_combo = max(_best_combo, _combo)
		gained = _score_gain()
		_score += gained
		_burst(T.GRE)
		_float_score(gained)
		_sfx("correct")
		if _combo == 5:
			_popup("火力全开!", _accent, true)
			_flash_screen(_accent, 0.28)
			_sfx("combo")
		elif _combo == 10:
			_popup("无懈可击!!", T.YEL, true)
			_flash_screen(T.YEL, 0.34)
			_sfx("combo")
		elif _combo >= 3:
			_popup("连击 x" + str(_combo), T.ORG, false)
		if _combo % 6 == 0:
			_grant_power()
	else:
		_combo = 0
		_sfx("wrong")
		if _shield_on:
			_shield_on = false
			_popup("护盾抵挡!", T.GRE)
			_flash_screen(T.GRE)
		else:
			_lives -= 1
			_set_shields(_lives)
			_shake(8.0)
			_flash_screen(T.MAG)

	# BOSS 连环突袭结算
	if _chain > 0:
		if correct:
			_chain -= 1
			if _chain == 0 and _chain_ok:
				_score += 200
				_popup("连环达成! +200", T.YEL)
				_float_score(200)
		else:
			_chain_ok = false
			_chain = 0
			_popup("连环中断", T.MAG)

	_flash(correct, missed, gained)
	_update_hud()
	_update_goal()

	var panel := _card_panel()
	if panel and is_instance_valid(panel):
		create_tween().tween_property(panel, "modulate:a", 0.18, 0.2)

	await get_tree().create_timer(1.1).timeout
	if not is_inside_tree():
		return
	_busy = false
	if _lives <= 0:
		if _mode == "endless": _end_endless()
		else: _end_lose()
	elif _mode == "campaign" and _answered >= _goal:
		_stage_clear()
	else:
		_draw_card()


func _grant_power() -> void:
	var pool := ["eye", "freeze", "shield"]
	var g: String = pool[randi() % pool.size()]
	_pw[g] = int(_pw.get(g, 0)) + 1
	_update_powerbar()
	_popup("获得道具：" + _pw_name(g), T.GRE)


func _score_gain() -> int:
	var spd := clampf(timerbar.value, 0.0, 1.0)          # 剩余时间越多反应越快
	var mult := 1.0 + 0.08 * float(mini(_combo - 1, 12)) # 连击线性加成
	if _combo >= 10:
		mult *= 1.35   # 里程碑：无懈可击
	elif _combo >= 5:
		mult *= 1.20   # 里程碑：火力全开
	var chain_mult := 1.5 if _chain > 0 else 1.0
	return int(round((60.0 + 140.0 * spd) * mult * chain_mult))


# ══════════════════════════════ 计时 ══════════════════════════════

func _time_limit() -> float:
	var base := _base_time
	if _chain > 0:
		base *= 0.8
	return clampf(base - 0.10 * float(_answered), 1.8, _base_time)

func _start_timer() -> void:
	timerbar.value = 1.0
	_stop_timer()
	_timer_tw = create_tween()
	_timer_tw.tween_property(timerbar, "value", 0.0, _time_limit())
	_timer_tw.tween_callback(_on_timeout)

func _stop_timer() -> void:
	if _timer_tw and _timer_tw.is_valid():
		_timer_tw.kill()

func _on_timeout() -> void:
	if _busy or _over or _frozen: return
	_resolve(-1)


# ══════════════════════════════ 卡片 / 反馈 ══════════════════════════════

func _kind_color(kind: String) -> Color:
	match kind:
		"短信": return T.CYA
		"来电": return T.MAG
		"通知": return T.YEL
		"好友": return T.GRE
		"群消息": return T.ORG
		_: return T.CYA


func _make_card(d: Dictionary) -> Control:
	var kc := _kind_color(str(d.get("kind", "")))
	var wrap := Control.new()
	wrap.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var p := PanelContainer.new()
	p.name = "CardPanel"
	p.anchor_left = 0.0
	p.anchor_top = 0.0
	p.anchor_right = 1.0
	p.anchor_bottom = 1.0
	p.offset_left = 0.0
	p.offset_right = 0.0
	p.offset_top = 0.0
	p.offset_bottom = 0.0
	var sb := T.box(T.BG2, kc.darkened(0.15), 1)
	sb.set_corner_radius_all(12)
	sb.shadow_color = Color(0, 0, 0, 0.4)
	sb.shadow_size = 10
	sb.shadow_offset = Vector2(0, 5)
	p.add_theme_stylebox_override("panel", sb)

	var m := MarginContainer.new()
	m.add_theme_constant_override("margin_left", 24)
	m.add_theme_constant_override("margin_right", 24)
	m.add_theme_constant_override("margin_top", 20)
	m.add_theme_constant_override("margin_bottom", 20)
	p.add_child(m)

	var v := VBoxContainer.new()
	v.add_theme_constant_override("separation", 16)
	m.add_child(v)

	var hb := HBoxContainer.new()
	hb.add_theme_constant_override("separation", 10)
	var kind := Label.new()
	kind.text = "【" + GameManager.clean(str(d.get("kind", "信息"))) + "】"
	kind.add_theme_color_override("font_color", kc)
	kind.add_theme_font_size_override("font_size", 15)
	_apply_font(kind)
	var frm := Label.new()
	frm.text = GameManager.clean(str(d.get("from", "")))
	frm.add_theme_color_override("font_color", T.TX2)
	frm.add_theme_font_size_override("font_size", 15)
	_apply_font(frm)
	frm.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	hb.add_child(kind)
	hb.add_child(frm)
	v.add_child(hb)

	var line := ColorRect.new()
	line.color = kc.darkened(0.2)
	line.custom_minimum_size = Vector2(0, 2)
	v.add_child(line)

	var body := Label.new()
	body.text = GameManager.clean(str(d.get("text", "")))
	body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	body.add_theme_color_override("font_color", T.TX1)
	body.add_theme_font_size_override("font_size", 22)
	_apply_font(body)
	body.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	v.add_child(body)
	wrap.add_child(p)
	return wrap


func _flash(correct: bool, missed: bool, gained: int) -> void:
	var is_scam := bool(_cur.get("scam", false))
	var col: Color
	var head := ""
	if missed:
		col = T.YEL
		head = "超时未处理！这是" + ("诈骗" if is_scam else "正常信息")
	elif correct:
		col = T.GRE
		head = ("识破诈骗！" if is_scam else "放行正确！") + "    +" + str(gained)
	else:
		col = T.MAG
		head = "看走眼了！这是" + ("诈骗，应当拦截" if is_scam else "正常信息，不该拦截")

	var p := PanelContainer.new()
	p.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	var sb := T.box(Color(col.r, col.g, col.b, 0.14), col, 2)
	sb.set_corner_radius_all(12)
	p.add_theme_stylebox_override("panel", sb)
	p.mouse_filter = Control.MOUSE_FILTER_IGNORE

	var m := MarginContainer.new()
	m.add_theme_constant_override("margin_left", 24)
	m.add_theme_constant_override("margin_right", 24)
	m.add_theme_constant_override("margin_top", 20)
	m.add_theme_constant_override("margin_bottom", 20)
	p.add_child(m)

	var v := VBoxContainer.new()
	v.alignment = BoxContainer.ALIGNMENT_CENTER
	v.add_theme_constant_override("separation", 14)
	m.add_child(v)

	var h := Label.new()
	h.text = head
	h.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	h.add_theme_color_override("font_color", col)
	h.add_theme_font_size_override("font_size", 23)
	_apply_font(h)
	v.add_child(h)

	var tagl := Label.new()
	tagl.text = "类型：" + GameManager.clean(str(_cur.get("tag", "")))
	tagl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tagl.add_theme_color_override("font_color", T.TX2)
	tagl.add_theme_font_size_override("font_size", 15)
	_apply_font(tagl)
	v.add_child(tagl)

	var tipl := Label.new()
	tipl.text = GameManager.clean(str(_cur.get("tip", "")))
	tipl.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	tipl.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	tipl.add_theme_color_override("font_color", T.TX1)
	tipl.add_theme_font_size_override("font_size", 15)
	_apply_font(tipl)
	v.add_child(tipl)

	card_layer.add_child(p)
	p.modulate.a = 0.0
	create_tween().tween_property(p, "modulate:a", 1.0, 0.15)


# ══════════════════════════════ HUD ══════════════════════════════

func _update_hud() -> void:
	score_lbl.text = "积分 " + str(_score)
	if _combo >= 2:
		combo_lbl.text = "连击 x" + str(_combo)
		var tw := create_tween()
		tw.tween_property(combo_lbl, "scale", Vector2(1.35, 1.35), 0.08)
		tw.tween_property(combo_lbl, "scale", Vector2.ONE, 0.08)
	else:
		combo_lbl.text = ""

func _update_goal() -> void:
	if _mode == "campaign":
		goalbar.show()
		goalbar.max_value = max(1, _goal)
		var tw := create_tween()
		tw.tween_property(goalbar, "value", float(min(_answered, _goal)), 0.25)
		var extra := "   连环x%d" % _chain if _chain > 0 else ""
		hud_wave.text = "清理 %d/%d%s" % [int(min(_answered, _goal)), _goal, extra]
	else:
		goalbar.hide()
		hud_wave.text = "波 " + str(_answered / 8 + 1)

func _set_shields(n: int) -> void:
	for c in shields.get_children():
		c.queue_free()
	shields.modulate = Color.WHITE
	var cap := Label.new()
	cap.text = "防御"
	cap.add_theme_color_override("font_color", T.TX2)
	cap.add_theme_font_size_override("font_size", 13)
	_apply_font(cap)
	shields.add_child(cap)
	for i in _maxlives:
		var l := Label.new()
		l.text = "◆"
		l.add_theme_font_size_override("font_size", 16)
		l.add_theme_color_override("font_color", T.GRE if i < n else T.BG3)
		_apply_font(l)
		shields.add_child(l)
	if n == 1:
		var tw := create_tween()
		tw.tween_property(shields, "modulate", Color(1, 0.5, 0.5), 0.2)
		tw.tween_property(shields, "modulate", Color.WHITE, 0.5)


# ══════════════════════════════ 特效 ══════════════════════════════

func _ensure_fx_layer() -> CanvasLayer:
	if _fx_layer != null and is_instance_valid(_fx_layer):
		return _fx_layer
	_fx_layer = CanvasLayer.new()
	_fx_layer.name = "FxLayer"
	_fx_layer.layer = 64
	add_child(_fx_layer)
	return _fx_layer


func _viewport_size() -> Vector2:
	return get_viewport().get_visible_rect().size


func _burst(c: Color) -> void:
	var layer := _ensure_fx_layer()
	var center := _viewport_size() * 0.5
	var hi := Color(c.r, c.g, c.b, 1.0).lightened(0.35)
	for _i in 22:
		var r := ColorRect.new()
		r.color = hi if _i % 3 == 0 else c
		var s := randf_range(6.0, 14.0)
		r.size = Vector2(s, s)
		r.position = center - r.size * 0.5
		r.mouse_filter = Control.MOUSE_FILTER_IGNORE
		layer.add_child(r)
		var a := randf_range(0.0, TAU)
		var dist := randf_range(70.0, 200.0)
		var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
		tw.tween_property(r, "position", center + Vector2(cos(a), sin(a)) * dist - r.size * 0.5, 0.55)
		tw.parallel().tween_property(r, "modulate:a", 0.0, 0.55)
		tw.parallel().tween_property(r, "scale", Vector2(0.2, 0.2), 0.55)
		tw.finished.connect(r.queue_free)


## 根节点全屏锚点无法靠 position 抖动，改为偏移题目区与底部操作区
func _shake(amp: float) -> void:
	var targets: Array[Control] = [card_layer, dock]
	var base: Dictionary = {}
	for t in targets:
		base[t] = Vector2(float(t.offset_left), float(t.offset_top))
	var tw := create_tween()
	for _j in 6:
		for t in targets:
			var b: Vector2 = base[t]
			var j := Vector2(randf_range(-amp, amp), randf_range(-amp, amp))
			tw.parallel().tween_property(t, "offset_left", int(b.x + j.x), 0.03)
			tw.parallel().tween_property(t, "offset_top", int(b.y + j.y), 0.03)
	for t in targets:
		var b: Vector2 = base[t]
		tw.parallel().tween_property(t, "offset_left", int(b.x), 0.04)
		tw.parallel().tween_property(t, "offset_top", int(b.y), 0.04)


func _popup(txt: String, col: Color, milestone: bool = false) -> void:
	var layer := _ensure_fx_layer()
	var wrap := Control.new()
	wrap.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	wrap.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(wrap)
	var l := Label.new()
	l.text = txt
	l.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	l.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	l.set_anchors_preset(Control.PRESET_CENTER_TOP)
	l.anchor_top = 0.36 if milestone else 0.40
	l.offset_left = -300.0
	l.offset_right = 300.0
	l.offset_top = -28.0
	l.offset_bottom = 28.0
	var fs := 36 if milestone else 26
	l.add_theme_font_size_override("font_size", fs)
	_apply_font(l)
	l.add_theme_color_override("font_color", col.lightened(0.15) if milestone else col)
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.75))
	l.add_theme_constant_override("outline_size", 4 if milestone else 2)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	wrap.add_child(l)
	l.modulate.a = 1.0
	l.scale = Vector2(0.6, 0.6) if milestone else Vector2.ONE
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	if milestone:
		tw.tween_property(l, "scale", Vector2(1.15, 1.15), 0.12)
		tw.tween_property(l, "scale", Vector2.ONE, 0.10)
		tw.tween_interval(0.55)
	else:
		tw.tween_interval(0.25)
	tw.tween_property(l, "modulate:a", 0.0, 0.65)
	tw.finished.connect(wrap.queue_free)


func _float_score(n: int) -> void:
	var layer := _ensure_fx_layer()
	var l := Label.new()
	l.text = "+" + str(n)
	l.add_theme_font_size_override("font_size", 28)
	_apply_font(l)
	l.add_theme_color_override("font_color", T.GRE.lightened(0.2))
	l.add_theme_color_override("font_outline_color", Color(0, 0, 0, 0.6))
	l.add_theme_constant_override("outline_size", 3)
	l.mouse_filter = Control.MOUSE_FILTER_IGNORE
	var vp := _viewport_size()
	l.position = Vector2(vp.x * 0.52, vp.y * 0.46)
	layer.add_child(l)
	var tw := create_tween().set_trans(Tween.TRANS_CUBIC).set_ease(Tween.EASE_OUT)
	tw.tween_property(l, "position:y", l.position.y - 72.0, 0.75)
	tw.parallel().tween_property(l, "modulate:a", 0.0, 0.75)
	tw.parallel().tween_property(l, "scale", Vector2(1.25, 1.25), 0.75)
	tw.finished.connect(l.queue_free)


func _flash_screen(c: Color, peak: float = 0.22) -> void:
	var layer := _ensure_fx_layer()
	var r := ColorRect.new()
	r.color = Color(c.r, c.g, c.b, 0.0)
	r.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	r.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(r)
	var tw := create_tween()
	tw.tween_method(
		func(a: float): r.color = Color(c.r, c.g, c.b, a),
		0.0, peak, 0.07
	)
	tw.tween_method(
		func(a: float): r.color = Color(c.r, c.g, c.b, a),
		peak, 0.0, 0.35
	)
	tw.finished.connect(r.queue_free)


# ══════════════════════════════ 结算 ══════════════════════════════

func _calc_stars(acc: float) -> int:
	var s := 1
	if acc >= 0.7: s = 2
	if acc >= 0.9: s = 3
	if _lives == _maxlives and acc >= 0.8: s = 3
	return s

func _rating_letter(acc: float) -> String:
	if acc >= 0.9: return "S"
	if acc >= 0.75: return "A"
	if acc >= 0.5: return "B"
	return "C"

func _rating_color(r: String) -> Color:
	match r:
		"S": return T.ORG
		"A": return T.GRE
		"B": return T.CYA
		_: return T.TX2

func _open_finish() -> void:
	fin.show()
	fin.modulate.a = 0.0
	fin.scale = Vector2(0.7, 0.7)
	fin.pivot_offset = fin.size * 0.5
	var tw := create_tween().set_trans(Tween.TRANS_BACK).set_ease(Tween.EASE_OUT)
	tw.tween_property(fin, "modulate:a", 1.0, 0.3)
	tw.parallel().tween_property(fin, "scale", Vector2.ONE, 0.3)


func _stage_clear() -> void:
	_over = true
	_stop_timer()
	block_btn.disabled = true; pass_btn.disabled = true
	_update_powerbar()
	_clear_layer()
	var acc := float(_correct) / float(max(_answered, 1))
	var stars := _calc_stars(acc)
	GameManager.save_stage_result(str(_stage.get("id", "")), stars)
	_open_finish()
	fin_title.text = "BOSS 击破！" if _is_boss else "关卡通关！"
	fin_title.add_theme_color_override("font_color", T.GRE)
	fin_rating.text = "★".repeat(stars) + "☆".repeat(max(0, 3 - stars))
	fin_rating.add_theme_color_override("font_color", T.YEL)
	fin_score.text = "积分 " + str(_score)
	fin_msg.text = "正确率 %d%% · 剩余防御 %d · 最高连击 x%d" % [int(round(acc * 100.0)), _lives, _best_combo]
	_win_buttons(_is_boss)
	_burst(T.YEL)
	_sfx("win")


func _end_lose() -> void:
	_over = true
	_stop_timer()
	block_btn.disabled = true; pass_btn.disabled = true
	_update_powerbar()
	_clear_layer()
	_open_finish()
	fin_title.text = "任务失败"
	fin_title.add_theme_color_override("font_color", T.MAG)
	fin_rating.text = ""
	fin_score.text = ""
	var acc := float(_correct) / float(max(_answered, 1))
	fin_msg.text = "防御耗尽 · 已清理 %d/%d · 正确率 %d%%，别气馁，再来一次" % [_answered, _goal, int(round(acc * 100.0))]
	for c in fin_btns.get_children(): c.queue_free()
	_fbtn("重试", T.ORG, _replay)
	_fbtn("选关", T.CYA, _to_select)


func _end_endless() -> void:
	_over = true
	_stop_timer()
	block_btn.disabled = true; pass_btn.disabled = true
	_update_powerbar()
	_clear_layer()
	var acc := float(_correct) / float(max(_answered, 1))
	var r := _rating_letter(acc)
	var rank := GameManager.add_endless_score(_score, r)
	_open_finish()
	fin_title.text = "新纪录！" if rank == 1 else "拦截结束"
	fin_title.add_theme_color_override("font_color", T.YEL if rank == 1 else T.TX1)
	fin_rating.text = "评级 " + r
	fin_rating.add_theme_color_override("font_color", _rating_color(r))
	fin_score.text = "积分 " + str(_score)
	var msg := "正确率 %d%% · 识破 %d 条 · 最高连击 x%d" % [int(round(acc * 100.0)), _correct, _best_combo]
	if rank > 0:
		msg += "  ·  本地第 %d 名" % rank
	fin_msg.text = msg
	for c in fin_btns.get_children(): c.queue_free()
	_fbtn("再来一局", T.GRE, _replay)
	_fbtn("返回菜单", T.TX2, _to_menu)
	if rank == 1:
		_popup("新纪录!", T.YEL)
	_burst(T.YEL)
	_sfx("win")


func _win_buttons(boss: bool) -> void:
	for c in fin_btns.get_children(): c.queue_free()
	if not boss and GameManager.game_stage + 1 < GameManager.STAGES.size():
		_fbtn("下一关 →", T.GRE, _next_stage)
	_fbtn("重玩", T.ORG, _replay)
	_fbtn("选关", T.CYA, _to_select)


func _fbtn(txt: String, c: Color, cb: Callable) -> void:
	var b := Button.new()
	b.text = txt
	b.custom_minimum_size = Vector2(120, 44)
	var n := T.box(c.darkened(0.5), c, 2); n.set_corner_radius_all(10)
	var h := T.box(c.darkened(0.35), c.lightened(0.2), 2); h.set_corner_radius_all(10)
	var pr := T.box(c.darkened(0.6), c, 2); pr.set_corner_radius_all(10)
	b.add_theme_stylebox_override("normal", n)
	b.add_theme_stylebox_override("hover", h)
	b.add_theme_stylebox_override("pressed", pr)
	b.add_theme_color_override("font_color", c)
	b.add_theme_color_override("font_hover_color", c.lightened(0.3))
	b.add_theme_font_size_override("font_size", 15)
	_apply_font(b)
	b.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
	b.pressed.connect(cb)
	fin_btns.add_child(b)


# ══════════════════════════════ 导航 ══════════════════════════════

func _next_stage() -> void:
	GameManager.game_stage += 1
	GameManager.go_to("res://scenes/game.tscn")

func _replay() -> void:
	GameManager.go_to("res://scenes/game.tscn")

func _to_select() -> void:
	GameManager.go_to("res://scenes/stage_select.tscn")

func _to_menu() -> void:
	GameManager.go_to("res://scenes/main_menu.tscn")
