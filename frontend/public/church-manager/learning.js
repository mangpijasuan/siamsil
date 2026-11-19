'use strict';
/*
 * Discipleship: Sunday school, Bible study and discipleship classes for Church Hub.
 * Developed by Siamsil Technologies, Inc.
 *
 * Loaded before app.js. Everything here is used lazily at run time, so it can rely on the helpers
 * and state that app.js defines (esc, table, form, db, state, saveDB, ...).
 *
 * Data (stored in the same browser record and backup as the rest of the church register):
 *   classes        {id, name, kind, audience, teacher, schedule, room, capacity, status, description}
 *   lessons        {id, class, order, title, passage, verse, materials, notes}
 *   enrollments    {id, class, member, status, enrolled, completedOn?}   status: Enrolled | Waitlist | Completed | Withdrawn
 *   classSessions  {id, class, date, lesson, present[], notes}
 * A learner's lesson progress is derived: a lesson counts when they were marked present at a session
 * that taught it.
 */
const LEARNING_KEYS = ['classes', 'lessons', 'enrollments', 'classSessions'];
const classKinds = ['Sunday School', 'Bible Study', 'Discipleship', 'Youth Group', 'Adult Class', 'Other'];
const isoDate = (d) => [d.getFullYear(), String(d.getMonth() + 1).padStart(2, '0'), String(d.getDate()).padStart(2, '0')].join('-');

/* ---------- sample data (fictional; Bible references only) ---------- */
function seedLearning(members) {
  const adults = members.filter((m) => m.stage === 'Adult');
  const youth = members.filter((m) => m.stage !== 'Adult');
  const now = new Date();
  const sundays = [0, 1, 2].map((i) => {
    const d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    d.setDate(d.getDate() - d.getDay() - 7 * i);
    return isoDate(d);
  });
  const defs = [
    { name: 'Children’s Sunday School', kind: 'Sunday School', audience: 'Ages 6–11', schedule: 'Sundays 9:00 AM', room: 'Room 104', capacity: 12, pool: youth.slice(0, 10), teacher: adults[1]?.id || '', description: 'Bible stories, memory verses and crafts for children.',
      lessons: [['In the Beginning', 'Genesis 1:1–5', 'Genesis 1:1'], ['Noah and the Ark', 'Genesis 6:9–22', 'Genesis 8:22'], ['David and Goliath', '1 Samuel 17:32–50', '1 Samuel 17:47'], ['The Good Samaritan', 'Luke 10:25–37', 'Luke 10:27']] },
    { name: 'Youth Bible Study', kind: 'Bible Study', audience: 'Ages 12–18', schedule: 'Wednesdays 6:30 PM', room: 'Youth Room', capacity: 15, pool: youth.slice(4), teacher: adults[3]?.id || '', description: 'A study through the Sermon on the Mount.',
      lessons: [['Salt and Light', 'Matthew 5:13–16', 'Matthew 5:16'], ['Treasure in Heaven', 'Matthew 6:19–24', 'Matthew 6:21'], ['Do Not Worry', 'Matthew 6:25–34', 'Matthew 6:33'], ['Build on the Rock', 'Matthew 7:24–29', 'Matthew 7:24']] },
    { name: 'Foundations of Faith', kind: 'Adult Class', audience: 'Adults', schedule: 'Sundays 11:30 AM', room: 'Fellowship Hall', capacity: 20, pool: adults.slice(0, 14), teacher: adults[5]?.id || '', description: 'Core beliefs and practices for new and growing believers.',
      lessons: [['Saved by Grace', 'Ephesians 2:1–10', 'Ephesians 2:8'], ['Learning to Pray', 'Matthew 6:5–15', 'Philippians 4:6'], ['Why Scripture Matters', '2 Timothy 3:14–17', '2 Timothy 3:16'], ['Life Together', 'Acts 2:42–47', 'Hebrews 10:24']] },
  ];
  const classes = [], lessons = [], enrollments = [], classSessions = [];
  const joined = isoDate(new Date(Date.now() - 30 * 864e5));
  defs.forEach((d, i) => {
    const id = 'C-' + String(i + 1).padStart(3, '0');
    classes.push({ id, name: d.name, kind: d.kind, audience: d.audience, teacher: d.teacher, schedule: d.schedule, room: d.room, capacity: d.capacity, status: 'Active', description: d.description });
    const own = d.lessons.map(([title, passage, verse], j) => ({ id: 'L-' + String(lessons.length + j + 1).padStart(3, '0'), class: id, order: j + 1, title, passage, verse, materials: '', notes: '' }));
    lessons.push(...own);
    d.pool.forEach((m) => enrollments.push({ id: 'EN-' + String(enrollments.length + 1).padStart(3, '0'), class: id, member: m.id, status: 'Enrolled', enrolled: joined }));
    const roster = d.pool.map((m) => m.id);
    sundays.forEach((date, k) => classSessions.push({ id: 'S-' + String(classSessions.length + 1).padStart(3, '0'), class: id, date, lesson: own[2 - k]?.id || '', present: roster.filter((_, n) => (n + k + i) % 5 !== 0), notes: '' }));
  });
  return { classes, lessons, enrollments, classSessions };
}

/** Older backups have no learning data: give them empty lists (sample registers get the sample classes). */
function normalize(d) {
  const missing = LEARNING_KEYS.some((k) => d[k] === undefined);
  LEARNING_KEYS.forEach((k) => { if (!Array.isArray(d[k])) d[k] = []; });
  if (missing && d.sample && d.members.length) Object.assign(d, seedLearning(d.members));
  return d;
}

/** Called from validBackup. The learning lists are optional so older backups still restore. */
function learningValid(d, records, text, isDate) {
  const optional = (v, check) => v === undefined || records(v, check);
  return optional(d.classes, (c) => text(c, ['name', 'kind', 'audience', 'teacher', 'schedule', 'room', 'description', 'status']) && ['Active', 'Archived'].includes(c.status) && Number.isSafeInteger(c.capacity) && c.capacity > 0)
    && optional(d.lessons, (l) => text(l, ['class', 'title', 'passage', 'verse', 'materials', 'notes']) && Number.isSafeInteger(l.order))
    && optional(d.enrollments, (e) => text(e, ['class', 'member', 'status', 'enrolled']) && isDate(e.enrolled) && ['Enrolled', 'Waitlist', 'Completed', 'Withdrawn'].includes(e.status))
    && optional(d.classSessions, (s) => text(s, ['class', 'date', 'lesson', 'notes']) && isDate(s.date) && Array.isArray(s.present) && s.present.every((x) => typeof x === 'string'));
}

/* ---------- helpers ---------- */
const classEnrollments = (id) => db.enrollments.filter((e) => e.class === id);
const seated = (id) => db.enrollments.filter((e) => e.class === id && e.status === 'Enrolled').length;
const classLessons = (id) => db.lessons.filter((l) => l.class === id).sort((a, b) => a.order - b.order || a.id.localeCompare(b.id));
const classSessionsOf = (id) => db.classSessions.filter((s) => s.class === id).sort((a, b) => b.date.localeCompare(a.date));
const teacherName = (c) => { const m = get('members', c.teacher); return m ? fullName(m) : '—'; };
const pct = (a, b) => (b ? Math.min(100, Math.round((a / b) * 100)) : 0);
const classLink = (text, id) => '<button type="button" class="record-link" data-action="select-class" data-key="' + esc(id) + '">' + esc(text) + '</button>';
const lessonLink = (text, id) => '<button type="button" class="record-link" data-action="select-lesson" data-key="' + esc(id) + '">' + esc(text) + '</button>';
const statusTone = (status) => (status === 'Enrolled' || status === 'Completed' || status === 'Active' ? 'good' : status === 'Waitlist' ? 'warn' : '');

function learnerStats(e) {
  const sessions = classSessionsOf(e.class);
  const attended = sessions.filter((s) => s.present.includes(e.member));
  const lessonIds = new Set(classLessons(e.class).map((l) => l.id));
  const done = new Set(attended.map((s) => s.lesson).filter((id) => lessonIds.has(id)));
  return { sessions: sessions.length, attended: attended.length, done: done.size, total: lessonIds.size };
}

/** Fill free seats from the waitlist, oldest first. */
function promote(next, classId) {
  const c = next.classes.find((x) => x.id === classId);
  if (!c) return;
  let seats = c.capacity - next.enrollments.filter((e) => e.class === classId && e.status === 'Enrolled').length;
  const waiting = next.enrollments.filter((e) => e.class === classId && e.status === 'Waitlist').sort((a, b) => a.enrolled.localeCompare(b.enrolled) || a.id.localeCompare(b.id));
  for (const e of waiting) {
    if (seats <= 0) break;
    e.status = 'Enrolled';
    seats--;
  }
}

function change(fn, message) {
  try {
    const next = structuredClone(db);
    fn(next);
    saveDB(next, message);
  } catch (error) {
    notice(error.message);
  }
}

function learningCleanup(next, kind, id) {
  if (kind === 'members') {
    next.enrollments = next.enrollments.filter((e) => e.member !== id);
    next.classSessions.forEach((s) => { s.present = s.present.filter((x) => x !== id); });
    next.classes.forEach((c) => { if (c.teacher === id) c.teacher = ''; });
    next.classes.forEach((c) => promote(next, c.id));
  } else if (kind === 'classes') {
    next.lessons = next.lessons.filter((l) => l.class !== id);
    next.enrollments = next.enrollments.filter((e) => e.class !== id);
    next.classSessions = next.classSessions.filter((s) => s.class !== id);
    state.selected.lessons = null;
  } else if (kind === 'lessons') {
    next.classSessions.forEach((s) => { if (s.lesson === id) s.lesson = ''; });
  }
}

/* ---------- form handlers (called from handleSubmit) ---------- */
const learningForms = {
  classes(next, data) {
    const capacity = Number(data.capacity);
    if (!Number.isSafeInteger(capacity) || capacity < 1) throw new Error('Enter a whole number for capacity.');
    if (!classKinds.includes(data.kind)) throw new Error('Choose a class type.');
    if (!['Active', 'Archived'].includes(data.status)) throw new Error('Choose a status.');
    if (data.teacher && !next.members.some((m) => m.id === data.teacher)) throw new Error('Choose a valid teacher.');
    const record = { name: data.name, kind: data.kind, audience: data.audience, teacher: data.teacher, schedule: data.schedule, room: data.room, capacity, status: data.status, description: data.description };
    const old = next.classes.find((c) => c.id === state.selected.classes);
    if (old) {
      if (seatedIn(next, old.id) > capacity) throw new Error('Capacity must cover the learners already enrolled.');
      Object.assign(old, record);
      promote(next, old.id);
    } else {
      const id = sequence(next.classes, 'C-');
      next.classes.push({ id, ...record });
      state.selected.classes = id;
      state.selected.lessons = null;
    }
    return { message: 'Class saved.' };
  },
  lessons(next, data) {
    const c = next.classes.find((x) => x.id === state.selected.classes);
    if (!c) throw new Error('Save a class first.');
    const old = next.lessons.find((l) => l.id === state.selected.lessons && l.class === c.id);
    let order = data.order === '' ? NaN : Number(data.order);
    if (!Number.isFinite(order)) order = old ? old.order : Math.max(0, ...next.lessons.filter((l) => l.class === c.id).map((l) => l.order)) + 1;
    if (!Number.isSafeInteger(order) || order < 1) throw new Error('Enter a whole number for the lesson order.');
    const record = { title: data.title, passage: data.passage, verse: data.verse, order, materials: data.materials, notes: data.notes };
    if (old) Object.assign(old, record);
    else next.lessons.push({ id: sequence(next.lessons, 'L-'), class: c.id, ...record });
    if (!old) state.selected.lessons = null;
    return { message: 'Lesson saved.' };
  },
  enroll(next, data) {
    const c = next.classes.find((x) => x.id === state.selected.classes);
    const m = next.members.find((x) => x.id === data.member);
    if (!c || !m) throw new Error('Choose a class and a member.');
    if (c.status !== 'Active') throw new Error('This class is archived.');
    const existing = next.enrollments.find((e) => e.class === c.id && e.member === m.id);
    if (existing && existing.status !== 'Withdrawn') throw new Error(fullName(m) + ' is already on this roster.');
    const status = seatedIn(next, c.id) >= c.capacity ? 'Waitlist' : 'Enrolled';
    if (existing) {
      Object.assign(existing, { status, enrolled: today() });
      delete existing.completedOn;
    } else {
      next.enrollments.push({ id: sequence(next.enrollments, 'EN-'), class: c.id, member: m.id, status, enrolled: today() });
    }
    return { message: status === 'Waitlist' ? 'The class is full. Added to the waitlist.' : 'Learner enrolled.' };
  },
  'class-session'(next, data, formElement) {
    const c = next.classes.find((x) => x.id === state.selected.classes);
    if (!c) throw new Error('Select a class first.');
    if (!isDate(data.date)) throw new Error('Choose a valid session date.');
    if (next.classSessions.some((s) => s.class === c.id && s.date === data.date)) throw new Error('A session is already recorded for this class on that date. Delete it first to record it again.');
    if (data.lesson && !next.lessons.some((l) => l.id === data.lesson && l.class === c.id)) throw new Error('Choose a lesson from this class.');
    const allowed = new Set(next.enrollments.filter((e) => e.class === c.id && e.status === 'Enrolled').map((e) => e.member));
    const present = [...new Set(new FormData(formElement).getAll('present'))].filter((x) => typeof x === 'string');
    if (present.some((x) => !allowed.has(x))) throw new Error('Mark attendance only for enrolled learners.');
    next.classSessions.push({ id: sequence(next.classSessions, 'S-'), class: c.id, date: data.date, lesson: data.lesson, present, notes: data.notes });
    return { message: 'Session recorded.' };
  },
};
const seatedIn = (data, id) => data.enrollments.filter((e) => e.class === id && e.status === 'Enrolled').length;

/* ---------- button actions ---------- */
function rosterRows(id) {
  return classEnrollments(id).filter((e) => e.status !== 'Withdrawn').map((e) => ({ e, m: get('members', e.member), st: learnerStats(e) }))
    .sort((a, b) => (fullName(a.m)).localeCompare(fullName(b.m)));
}
const learningActions = {
  'select-class'(id) { state.selected.classes = id; state.selected.lessons = null; state.search = ''; render(); },
  'select-lesson'(id) { state.selected.lessons = id; render(); },
  'check-all'(key, el) { el.closest('form').querySelectorAll('[name=present]').forEach((box) => { box.checked = true; }); },
  'enroll-complete'(id) {
    change((next) => {
      const e = next.enrollments.find((x) => x.id === id);
      if (!e || e.status !== 'Enrolled') throw new Error('Only enrolled learners can be marked completed.');
      e.status = 'Completed';
      e.completedOn = today();
      promote(next, e.class);
    }, 'Marked as completed.');
  },
  'enroll-withdraw'(id) {
    change((next) => {
      const e = next.enrollments.find((x) => x.id === id);
      if (!e || !['Enrolled', 'Waitlist'].includes(e.status)) throw new Error('This learner cannot be withdrawn.');
      e.status = 'Withdrawn';
      promote(next, e.class);
    }, 'Learner withdrawn.');
  },
  'enroll-remove'(id) {
    change((next) => {
      const e = next.enrollments.find((x) => x.id === id);
      if (!e) return;
      next.enrollments = next.enrollments.filter((x) => x.id !== id);
      promote(next, e.class);
    }, 'Removed from the roster.');
  },
  certificate(id) {
    const e = get('enrollments', id), c = e && get('classes', e.class), m = e && get('members', e.member);
    if (!e || !c || !m || e.status !== 'Completed') return;
    printSheet('Certificate of Completion',
      '<div class="certificate"><p>' + esc(db.settings.church) + '</p><p>This certifies that</p><h2>' + esc(fullName(m)) + '</h2><p>has successfully completed</p><h3>' + esc(c.name) + '</h3><p>' + esc(c.kind) + (c.audience ? ' · ' + esc(c.audience) : '') + '</p><p>' + date(e.completedOn || today()) + '</p><div class="signatures"><span>Teacher · ' + esc(teacherName(c)) + '</span><span>Pastor / Leader</span></div></div>');
  },
  'roster-print'(id) {
    const c = get('classes', id);
    if (!c) return;
    printSheet('Class roster · ' + c.name,
      '<h2>' + esc(db.settings.church) + '</h2><p>' + esc([c.kind, c.audience, c.schedule, c.room].filter(Boolean).join(' · ')) + '</p><p>Teacher: ' + esc(teacherName(c)) + '</p>' +
      table(['Learner', 'Status', 'Attended', 'Lessons'], rosterRows(id).map(({ e, m, st }) => [esc(fullName(m)), esc(e.status), st.attended + ' / ' + st.sessions, st.done + ' / ' + st.total])));
  },
  'roster-csv'(id) {
    const c = get('classes', id);
    if (!c) return;
    const data = [['Class', 'Member ID', 'Learner', 'Status', 'Enrolled', 'Sessions attended', 'Sessions held', 'Lessons completed', 'Lessons total'],
      ...rosterRows(id).map(({ e, m, st }) => [c.name, e.member, fullName(m), e.status, e.enrolled, st.attended, st.sessions, st.done, st.total])];
    download('﻿' + data.map((row) => row.map(csvValue).join(',')).join('\r\n'), 'class-roster-' + c.id + '-' + today() + '.csv', 'text/csv;charset=utf-8');
  },
};

/* ---------- page ---------- */
function classFields(c = {}) {
  const teachers = [['', 'Choose a teacher'], ...[...db.members].filter((m) => m.status !== 'Deceased').sort((a, b) => fullName(a).localeCompare(fullName(b))).map((m) => [m.id, fullName(m)])];
  return field('Class name', 'name', c.name, { required: true, full: true }) + field('Type', 'kind', c.kind || 'Sunday School', { options: classKinds, required: true }) + field('Status', 'status', c.status || 'Active', { options: ['Active', 'Archived'] }) +
    field('Age group / audience', 'audience', c.audience) + field('Teacher', 'teacher', c.teacher, { options: teachers }) +
    field('Schedule', 'schedule', c.schedule) + field('Room / place', 'room', c.room) + field('Capacity', 'capacity', c.capacity || 20, { type: 'number', min: 1, step: 1, required: true }) +
    field('Description', 'description', c.description, { area: true, full: true });
}

function discipleship() {
  const c = get('classes', state.selected.classes);
  const list = filterList(db.classes.filter((x) => !state.classKind || x.kind === state.classKind), (x) => [x.name, x.kind, x.audience, teacherName(x)].join(' '))
    .sort((a, b) => (a.status === b.status ? 0 : a.status === 'Active' ? -1 : 1) || a.name.localeCompare(b.name));
  const active = db.classes.filter((x) => x.status === 'Active');
  const activeIds = new Set(active.map((x) => x.id));
  const learners = new Set(db.enrollments.filter((e) => e.status === 'Enrolled' && activeIds.has(e.class)).map((e) => e.member));
  const month = today().slice(0, 7);
  const average = db.classSessions.length ? Math.round((sum(db.classSessions.map((s) => ({ n: s.present.length })), 'n') / db.classSessions.length) * 10) / 10 : 0;

  let detail = '';
  if (c) {
    const roster = rosterRows(c.id);
    const onRoster = new Set(classEnrollments(c.id).filter((e) => e.status !== 'Withdrawn').map((e) => e.member));
    const candidates = [...db.members].filter((m) => m.status !== 'Deceased' && !onRoster.has(m.id)).sort((a, b) => fullName(a).localeCompare(fullName(b)));
    const waiting = roster.filter(({ e }) => e.status === 'Waitlist').length;
    const rosterPanel = panel('Roster · ' + c.name,
      note(seated(c.id) + ' of ' + c.capacity + ' seats filled' + (waiting ? ' · ' + waiting + ' on the waitlist' : '') + '. A full class adds new learners to the waitlist automatically.') +
      form('enroll', field('Add a learner', 'member', '', { options: [['', 'Choose a member'], ...candidates.map((m) => [m.id, fullName(m) + ' · ' + m.id])], required: true, full: true }), 'Enroll') +
      '<div class="spaced">' + table(['Learner', 'Status', 'Attended', 'Lessons', ''], roster.map(({ e, m, st }) => [
        m ? recordLink(fullName(m), 'members', m.id) : 'Removed member', badge(e.status, statusTone(e.status)), st.attended + ' / ' + st.sessions,
        st.done + ' / ' + st.total + (st.total ? ' · ' + pct(st.done, st.total) + '%' : ''),
        '<div class="actions">' + (e.status === 'Enrolled' ? btn('Complete', 'enroll-complete', e.id, 'secondary small') : '') + (e.status === 'Completed' ? btn('Certificate', 'certificate', e.id, 'secondary small', 'print') : '') +
          (['Enrolled', 'Waitlist'].includes(e.status) ? btn('Withdraw', 'enroll-withdraw', e.id, 'secondary small') : '') + btn('Remove', 'enroll-remove', e.id, 'secondary small') + '</div>',
      ])) + '</div>');

    const lessons = classLessons(c.id);
    const lesson = lessons.find((l) => l.id === state.selected.lessons);
    const lessonPanel = panel('Lessons · ' + c.name,
      table(['#', 'Lesson', 'Passage', 'Memory verse'], lessons.map((l) => [l.order, lessonLink(l.title, l.id), esc(l.passage || '—'), esc(l.verse || '—')])) +
      '<div class="spaced"><h3>' + (lesson ? 'Edit lesson' : 'New lesson') + '</h3>' +
      form('lessons', field('Title', 'title', lesson?.title, { required: true, full: true }) + field('Bible passage', 'passage', lesson?.passage) + field('Memory verse', 'verse', lesson?.verse) +
        field('Order', 'order', lesson ? String(lesson.order) : '', { type: 'number', min: 1, step: 1 }) + field('Materials / link', 'materials', lesson?.materials) + field('Teacher notes', 'notes', lesson?.notes, { area: true, full: true }),
        'Save Lesson', (lesson ? btn('New Lesson', 'new', 'lessons', 'secondary') + delBtn('lessons', lesson.id) : '')) + '</div>');

    const enrolled = roster.filter(({ e }) => e.status === 'Enrolled').map(({ m }) => m).filter(Boolean);
    const sessionForm = '<form data-form="class-session"><div class="fields">' + field('Date', 'date', today(), { type: 'date', required: true }) +
      field('Lesson taught', 'lesson', '', { options: [['', 'No lesson linked'], ...lessons.map((l) => [l.id, l.order + '. ' + l.title])] }) +
      '<fieldset class="full checks"><legend>Present (' + enrolled.length + ' enrolled)</legend>' +
      (enrolled.length ? enrolled.map((m) => '<label class="check-label"><input type="checkbox" name="present" value="' + esc(m.id) + '"> ' + esc(fullName(m)) + '</label>').join('') : '<span class="muted">Enroll learners to take attendance.</span>') +
      '</fieldset>' + field('Notes', 'notes', '', { area: true, full: true }) + '</div><div class="actions spaced">' + submit('Record Session') + (enrolled.length ? btn('Select All', 'check-all', '', 'secondary') : '') + '</div></form>';
    const lessonTitle = (id) => { const l = lessons.find((x) => x.id === id); return l ? l.order + '. ' + l.title : '—'; };
    const sessionPanel = panel('Session history', table(['Date', 'Lesson', 'Present', 'Notes', ''],
      classSessionsOf(c.id).map((s) => [date(s.date), esc(lessonTitle(s.lesson)), s.present.length, esc(s.notes || '—'), delBtn('classSessions', s.id, true)])));
    detail = '<div class="two-col">' + rosterPanel + lessonPanel + '</div><div class="two-col">' + panel('Record a session', sessionForm) + sessionPanel + '</div>';
  }

  const report = table(['Class', 'Sessions', 'Avg. present', 'Avg. attendance', 'Lessons taught', 'Completed'], db.classes.map((x) => {
    const sessions = classSessionsOf(x.id), lessons = classLessons(x.id), seats = seated(x.id);
    const averagePresent = sessions.length ? sum(sessions.map((s) => ({ n: s.present.length })), 'n') / sessions.length : 0;
    const taught = new Set(sessions.map((s) => s.lesson).filter((id) => lessons.some((l) => l.id === id))).size;
    return [classLink(x.name, x.id), sessions.length, sessions.length ? String(Math.round(averagePresent * 10) / 10) : '—', sessions.length && seats ? pct(averagePresent, seats) + '%' : '—', taught + ' / ' + lessons.length, db.enrollments.filter((e) => e.class === x.id && e.status === 'Completed').length];
  }));

  return title('Discipleship', 'Sunday school, Bible study and discipleship classes',
    (c ? btn('Print Roster', 'roster-print', c.id, 'secondary', 'print') + btn('Roster CSV', 'roster-csv', c.id, 'secondary', 'file') : '') + btn('New Class', 'new', 'classes', 'gold', 'add')) +
    '<div class="stats" style="--count:4">' + stat('Active classes', active.length, db.classes.length - active.length + ' archived') + stat('Learners', learners.size, 'Enrolled in active classes') +
      stat('Sessions this month', db.classSessions.filter((s) => s.date.startsWith(month)).length, 'Across all classes') + stat('Average attendance', average, 'Learners present per session') + '</div>' +
    '<div class="filters">' + selector('classKind', state.classKind, [['', 'All types'], ...classKinds], 'Type') + search('Class, type, age group or teacher') + '</div>' +
    '<div class="two-col">' + panel('Classes & groups', table(['Class', 'Type', 'Teacher', 'Seats', 'Status'], list.map((x) => [classLink(x.name, x.id), esc(x.kind), esc(teacherName(x)), seated(x.id) + ' / ' + x.capacity, badge(x.status, statusTone(x.status))]))) +
      panel(c ? 'Class details · ' + c.id : 'New class', form('classes', classFields(c), 'Save Record', delBtn('classes', c?.id))) + '</div>' +
    detail + panel('Attendance & progress by class', report);
}
