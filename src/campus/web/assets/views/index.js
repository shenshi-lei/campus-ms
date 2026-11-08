import {
  attendanceView,
  auditView,
  classesView,
  coursesView,
  dashboardView,
  dormsView,
  enrollmentsView,
  feesView,
  noticesView,
  reportsView,
  scoresView,
  studentsView,
  teachersView,
} from "./legacy.js";
import { calendarView } from "./calendar.js";
import { leavesView } from "./leaves.js";
import { notificationsView } from "./notifications.js";
import { schedulesView } from "./timetable.js";
import { settingsView } from "./settings.js";

export const VIEWS = {
  dashboard: dashboardView,
  reports: reportsView,
  students: studentsView,
  teachers: teachersView,
  classes: classesView,
  courses: coursesView,
  enrollments: enrollmentsView,
  scores: scoresView,
  attendance: attendanceView,
  schedules: schedulesView,
  dorms: dormsView,
  fees: feesView,
  leaves: leavesView,
  calendar: calendarView,
  notifications: notificationsView,
  notices: noticesView,
  settings: settingsView,
  audit: auditView,
};
