import { ApiError, api } from "../api.js";
import { el, toast } from "../ui.js";

const state = {
  user: null,
  permissions: new Set(),
  nav: [],
  scope: {},
  view: "dashboard",
  days: 30,
  lookupsLoaded: false,
  lookups: {
    classes: [],
    teachers: [],
    courses: [],
    students: [],
    subjects: [],
    departments: [],
    semesters: [],
    groups: [],
  },
};

function can(permission) {
  return state.permissions.has(permission);
}

function canAny(...permissions) {
  return permissions.some((permission) => can(permission));
}

function navItems() {
  return state.nav.flatMap((group) => group.items);
}

const ROLE_LABEL = { admin: "管理员", teacher: "教师", student: "学生" };
const GENDER_LABEL = { male: "男", female: "女", unknown: "未知" };
const ATTENDANCE_LABEL = { present: "出勤", late: "迟到", absent: "缺勤", leave: "请假" };
const FEE_LABEL = { unpaid: "未缴", paid: "已缴", refunded: "已退" };
const STUDENT_STATUS_LABEL = {
  active: "在读",
  suspended: "休学",
  withdrawn: "退学",
  graduated: "毕业",
  retained: "保留学籍",
};
const CLASS_ROLE_LABEL = {
  none: "无",
  monitor: "班长",
  vice_monitor: "副班长",
  secretary: "团支书",
  study: "学习委员",
  life: "生活委员",
};
const RESIDENCE_LABEL = { boarding: "住校", day: "走读" };
const EMPLOYMENT_LABEL = {
  active: "在职",
  part_time: "兼职",
  retired: "退休",
  resigned: "离职",
};
const STAFF_TYPE_LABEL = {
  permanent: "编制",
  contract: "合同",
  part_time: "兼职",
  intern: "实习",
};
const EDUCATION_LABEL = {
  bachelor: "本科",
  master: "硕士",
  doctor: "博士",
  other: "其他",
};
const SEMESTER_STATUS_LABEL = { planned: "未开始", active: "进行中", closed: "已结束" };
const LEAVE_TYPE_LABEL = {
  personal: "事假",
  sick: "病假",
  business: "公出",
  compensatory: "调休",
  bereavement: "婚丧",
  maternity: "产假",
  other: "其他",
};
const LEAVE_STATUS_LABEL = {
  pending: "待审批",
  approved: "已通过",
  rejected: "已驳回",
  cancelled: "已撤销",
};
const AUDIENCE_LABEL = {
  all: "全校",
  teacher: "教师",
  student: "学生",
  class: "班级",
  group: "群组",
};
const COURSE_TYPE_LABEL = {
  required: "必修",
  elective: "选修",
  practice: "实践",
  public: "公选",
};
const ASSESSMENT_LABEL = { exam: "考试", check: "考查", paper: "论文", project: "项目" };
const SCHEDULE_STATUS_LABEL = { active: "正常", cancelled: "停课" };
const WEEKDAY_LABEL = ["", "周一", "周二", "周三", "周四", "周五", "周六", "周日"];

const PAGE_META = {
  dashboard: { title: "仪表盘", subtitle: "全校运行态势、风险预警与个人待办" },
  reports: { title: "报表", subtitle: "教师工作量、学科分析与班级对比" },
  students: { title: "学生管理", subtitle: "学籍档案、班级归属与在册状态" },
  teachers: { title: "教师管理", subtitle: "师资档案与院系信息" },
  classes: { title: "班级管理", subtitle: "班级设置与班主任安排" },
  courses: { title: "课程管理", subtitle: "开课计划、容量与任课教师" },
  enrollments: { title: "选课管理", subtitle: "选课记录与退课处理" },
  scores: { title: "成绩管理", subtitle: "平时分、考试分与总评" },
  attendance: { title: "考勤管理", subtitle: "按课程与日期登记出勤" },
  schedules: { title: "课表", subtitle: "按星期与节次查看排课" },
  dorms: { title: "宿舍管理", subtitle: "楼栋、房间与床位分配" },
  fees: { title: "缴费管理", subtitle: "费用项目、金额与缴纳状态" },
  leaves: { title: "请假", subtitle: "申请、审批与考勤联动" },
  calendar: { title: "日程", subtitle: "会议、活动、考试与个人事项" },
  notifications: { title: "消息中心", subtitle: "审批待办、日程提醒与系统消息" },
  notices: { title: "通知", subtitle: "全校、班级与个人通知" },
  settings: { title: "系统设置", subtitle: "组织、权限、群组、审批流程与参数" },
  audit: { title: "审计日志", subtitle: "写操作留痕与导出记录" },
};
function option(value, label) {
  return el("option", { value: String(value), text: label });
}

function withEmpty(options, label) {
  return [{ value: "", label }, ...options];
}

function courseOptions() {
  return state.lookups.courses.map((item) => ({
    value: item.id,
    label: `${item.code} ${item.name}`,
  }));
}

function studentOptions() {
  return state.lookups.students.map((item) => ({
    value: item.id,
    label: `${item.student_no} ${item.name}`,
  }));
}

function teacherOptions() {
  return state.lookups.teachers.map((item) => ({
    value: item.id,
    label: `${item.teacher_no} ${item.name}`,
  }));
}

function classOptions() {
  return state.lookups.classes.map((item) => ({ value: item.id, label: item.name }));
}

function subjectOptions() {
  return state.lookups.subjects.map((item) => ({
    value: item.id,
    label: `${item.code} ${item.name}`,
  }));
}

function departmentOptions() {
  return state.lookups.departments.map((item) => ({ value: item.id, label: item.name }));
}

function groupOptions() {
  return state.lookups.groups.map((item) => ({ value: item.id, label: item.name }));
}

function semesterOptions() {
  return state.lookups.semesters.map((item) => ({
    value: item.id,
    label: `${item.name}${item.is_current ? "（当前）" : ""}`,
  }));
}

function mapName(kind, id) {
  const key = {
    class: "classes",
    teacher: "teachers",
    course: "courses",
    student: "students",
    subject: "subjects",
    department: "departments",
    group: "groups",
  }[kind];
  const row = state.lookups[key].find((item) => item.id === id);
  return row ? row.name || row.student_no || row.code : `#${id}`;
}

async function loadLookups() {
  const [classes, teachers, courses, students, subjects, departments, semesters, groups] =
    await Promise.all([
      api.get("/classes"),
      api.get("/teachers?page_size=100"),
      api.get("/courses?page_size=100"),
      can("student:read") ? api.get("/students?page_size=100") : Promise.resolve({ items: [] }),
      can("subject:read") ? api.get("/org/subjects") : Promise.resolve([]),
      can("department:read") ? api.get("/org/departments") : Promise.resolve([]),
      can("semester:read") ? api.get("/org/semesters") : Promise.resolve([]),
      can("group:read") ? api.get("/groups") : Promise.resolve([]),
    ]);
  state.lookups = {
    classes,
    teachers: teachers.items,
    courses: courses.items,
    students: students.items,
    subjects,
    departments,
    semesters,
    groups,
  };
  state.lookupsLoaded = true;
}

async function ensureLookups(force = false) {
  if (state.lookupsLoaded && !force) return;
  await loadLookups();
}

let unauthorizedHandler = () => {};

export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

export function handleError(error) {
  if (error instanceof ApiError && error.status === 401) {
    unauthorizedHandler();
    toast("登录已过期，请重新登录", "error");
    return;
  }
  toast(error?.message || "操作失败", "error");
}

export {
  state,
  can,
  canAny,
  navItems,
  PAGE_META,
  ROLE_LABEL,
  GENDER_LABEL,
  ATTENDANCE_LABEL,
  FEE_LABEL,
  STUDENT_STATUS_LABEL,
  CLASS_ROLE_LABEL,
  RESIDENCE_LABEL,
  EMPLOYMENT_LABEL,
  STAFF_TYPE_LABEL,
  EDUCATION_LABEL,
  SEMESTER_STATUS_LABEL,
  LEAVE_TYPE_LABEL,
  LEAVE_STATUS_LABEL,
  AUDIENCE_LABEL,
  COURSE_TYPE_LABEL,
  ASSESSMENT_LABEL,
  SCHEDULE_STATUS_LABEL,
  WEEKDAY_LABEL,
  option,
  withEmpty,
  courseOptions,
  studentOptions,
  teacherOptions,
  classOptions,
  subjectOptions,
  departmentOptions,
  semesterOptions,
  groupOptions,
  mapName,
  loadLookups,
  ensureLookups,
};
