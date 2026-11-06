-- Fictional demo data for two independent schools. NOT real student information.
-- Requires migration 00001. Auth users are NOT created here (use local Auth UI / scripts).

insert into public.schools (id, name, slug, contact_details, status, configuration)
values
  (
    '11111111-1111-1111-1111-111111111111',
    'Kigali Hills Secondary School (Demo)',
    'kigali-hills-demo',
    '{"address":"KG 123 St, Kigali","phone":"+250 788 000 001","email":"admin@kigali-hills.demo"}'::jsonb,
    'active',
    '{"portals":{"student":false,"guardian":false},"ai_comments":false}'::jsonb
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'Lakeview Secondary School (Demo)',
    'lakeview-demo',
    '{"address":"RN3, Musanze","phone":"+250 788 000 002","email":"admin@lakeview.demo"}'::jsonb,
    'active',
    '{"portals":{"student":false,"guardian":false},"ai_comments":false}'::jsonb
  );

-- Academic year + default 3 terms × 3 periods for school 1
insert into public.academic_years (id, school_id, name, start_date, end_date, status)
values
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '11111111-1111-1111-1111-111111111111', '2025-2026', '2025-09-01', '2026-07-31', 'active'),
  ('aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', '22222222-2222-2222-2222-222222222222', '2025-2026', '2025-09-01', '2026-07-31', 'active');

insert into public.terms (id, school_id, academic_year_id, term_number, name, start_date, end_date, status)
values
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb11', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 1, 'Term 1', '2025-09-01', '2025-12-15', 'active'),
  ('bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb21', '22222222-2222-2222-2222-222222222222', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', 1, 'Term 1', '2025-09-01', '2025-12-15', 'active');

insert into public.reporting_periods (id, school_id, term_id, period_number, name, start_date, end_date, deadlines, status)
values
  (
    'cccccccc-cccc-cccc-cccc-cccccccccc11',
    '11111111-1111-1111-1111-111111111111',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb11',
    1,
    'Period 1',
    '2025-09-01',
    '2025-10-15',
    '{"assessment_entry":"2025-10-10","teacher_submission":"2025-10-12","class_teacher_review":"2025-10-14","approval":"2025-10-15","publication":"2025-10-16"}'::jsonb,
    'open'
  ),
  (
    'cccccccc-cccc-cccc-cccc-cccccccccc21',
    '22222222-2222-2222-2222-222222222222',
    'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbb21',
    1,
    'Period 1',
    '2025-09-01',
    '2025-10-15',
    '{"assessment_entry":"2025-10-10"}'::jsonb,
    'open'
  );

-- Curricula: O-Level, A-Level MS, Legacy S6 for school 1
insert into public.curricula (id, school_id, academic_year_id, name, level, configuration)
values
  ('dddddddd-dddd-dddd-dddd-dddddddddd01', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'O-Level 2025', 'olevel', '{}'::jsonb),
  ('dddddddd-dddd-dddd-dddd-dddddddddd02', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'A-Level MS 2025', 'alevel', '{"streams":["MS1","MS2"]}'::jsonb),
  ('dddddddd-dddd-dddd-dddd-dddddddddd03', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'S6 Legacy 2025', 'legacy_s6', '{"note":"Transitional cohort curriculum"}'::jsonb),
  ('dddddddd-dddd-dddd-dddd-dddddddddd21', '22222222-2222-2222-2222-222222222222', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', 'O-Level 2025', 'olevel', '{}'::jsonb);

insert into public.grades (id, school_id, curriculum_id, name, level, ordering)
values
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd01', 'S1', 'olevel', 1),
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee02', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd01', 'S2', 'olevel', 2),
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee03', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd01', 'S3', 'olevel', 3),
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd02', 'S4', 'alevel', 4),
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee05', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd02', 'S5', 'alevel', 5),
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd03', 'S6', 'legacy_s6', 6),
  ('eeeeeeee-eeee-eeee-eeee-eeeeeeeeee21', '22222222-2222-2222-2222-222222222222', 'dddddddd-dddd-dddd-dddd-dddddddddd21', 'S1', 'olevel', 1);

insert into public.combinations (id, school_id, curriculum_id, code, name, description)
values
  ('ffffffff-ffff-ffff-ffff-ffffffffff01', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd02', 'MS1', 'Mathematics Sciences 1', 'Configurable MS1 combination'),
  ('ffffffff-ffff-ffff-ffff-ffffffffff02', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd02', 'MS2', 'Mathematics Sciences 2', 'Configurable MS2 combination'),
  ('ffffffff-ffff-ffff-ffff-ffffffffff03', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd03', 'MPC', 'Maths Physics Computer Science', 'Legacy S6 — confirm vs PCM with school'),
  ('ffffffff-ffff-ffff-ffff-ffffffffff04', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd03', 'PCM', 'Physics Chemistry Mathematics', 'Legacy S6'),
  ('ffffffff-ffff-ffff-ffff-ffffffffff05', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd03', 'MCB', 'Mathematics Chemistry Biology', 'Legacy S6'),
  ('ffffffff-ffff-ffff-ffff-ffffffffff06', '11111111-1111-1111-1111-111111111111', 'dddddddd-dddd-dddd-dddd-dddddddddd03', 'PCB', 'Physics Chemistry Biology', 'Legacy S6');

-- Sample subjects (school-configurable seed, not national law)
insert into public.subjects (id, school_id, name, code, category)
values
  ('99999999-9999-9999-9999-999999990001', '11111111-1111-1111-1111-111111111111', 'Mathematics', 'MATH', 'core'),
  ('99999999-9999-9999-9999-999999990002', '11111111-1111-1111-1111-111111111111', 'Physics', 'PHY', 'core'),
  ('99999999-9999-9999-9999-999999990003', '11111111-1111-1111-1111-111111111111', 'Chemistry', 'CHEM', 'core'),
  ('99999999-9999-9999-9999-999999990004', '11111111-1111-1111-1111-111111111111', 'Biology', 'BIO', 'core'),
  ('99999999-9999-9999-9999-999999990005', '11111111-1111-1111-1111-111111111111', 'English', 'ENG', 'core'),
  ('99999999-9999-9999-9999-999999990006', '11111111-1111-1111-1111-111111111111', 'ICT', 'ICT', 'minor'),
  ('99999999-9999-9999-9999-999999990007', '11111111-1111-1111-1111-111111111111', 'Computer Science', 'CS', 'core'),
  ('99999999-9999-9999-9999-999999990101', '22222222-2222-2222-2222-222222222222', 'Mathematics', 'MATH', 'core'),
  ('99999999-9999-9999-9999-999999990102', '22222222-2222-2222-2222-222222222222', 'English', 'ENG', 'core');

insert into public.classes (id, school_id, academic_year_id, grade_id, combination_id, name, status)
values
  ('12121212-1212-1212-1212-121212121201', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee01', null, 'S1A', 'active'),
  ('12121212-1212-1212-1212-121212121202', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee04', 'ffffffff-ffff-ffff-ffff-ffffffffff01', 'S4 MS1A', 'active'),
  ('12121212-1212-1212-1212-121212121203', '11111111-1111-1111-1111-111111111111', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee06', 'ffffffff-ffff-ffff-ffff-ffffffffff03', 'S6 MPC', 'active'),
  ('12121212-1212-1212-1212-121212121221', '22222222-2222-2222-2222-222222222222', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeee21', null, 'S1A', 'active');

insert into public.students (id, school_id, student_code, full_name, status)
values
  ('13131313-1313-1313-1313-131313131301', '11111111-1111-1111-1111-111111111111', 'KH-S1-001', 'Alex Uwase (Demo)', 'active'),
  ('13131313-1313-1313-1313-131313131302', '11111111-1111-1111-1111-111111111111', 'KH-S4-001', 'Brian Niyonsenga (Demo)', 'active'),
  ('13131313-1313-1313-1313-131313131321', '22222222-2222-2222-2222-222222222222', 'LV-S1-001', 'Claire Mukamana (Demo)', 'active');

insert into public.enrollments (school_id, student_id, academic_year_id, class_id, start_date, status)
values
  ('11111111-1111-1111-1111-111111111111', '13131313-1313-1313-1313-131313131301', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '12121212-1212-1212-1212-121212121201', '2025-09-01', 'active'),
  ('11111111-1111-1111-1111-111111111111', '13131313-1313-1313-1313-131313131302', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa1', '12121212-1212-1212-1212-121212121202', '2025-09-01', 'active'),
  ('22222222-2222-2222-2222-222222222222', '13131313-1313-1313-1313-131313131321', 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaa2', '12121212-1212-1212-1212-121212121221', '2025-09-01', 'active');

-- Default incident types for school 1 (configurable defaults, not national rules)
insert into public.incident_types (school_id, name, default_deduction)
values
  ('11111111-1111-1111-1111-111111111111', 'Shouting', 2),
  ('11111111-1111-1111-1111-111111111111', 'Lateness', 2),
  ('11111111-1111-1111-1111-111111111111', 'Changing place in class', 3),
  ('11111111-1111-1111-1111-111111111111', 'Unsuitable shoes', 2),
  ('11111111-1111-1111-1111-111111111111', 'Communication language violation', 2),
  ('11111111-1111-1111-1111-111111111111', 'Other violation', 2);

insert into public.grading_policies (id, school_id, name, version, policy_configuration)
values (
  '14141414-1414-1414-1414-141414141401',
  '11111111-1111-1111-1111-111111111111',
  'Default weighted',
  1,
  '{
    "rounding_mode":"ROUND_HALF_UP",
    "display_places":2,
    "require_weights_sum_100":true,
    "behavior_base":40,
    "rank_policy":"competition",
    "allow_provisional_publication":false
  }'::jsonb
);

-- Phase 2: assessment categories (school defaults, not national rules)
insert into public.assessment_categories
  (school_id, name, code, default_maximum_marks, default_weight, ordering)
values
  ('11111111-1111-1111-1111-111111111111', 'Quizzes', 'QUIZ', 20, 0.1000, 1),
  ('11111111-1111-1111-1111-111111111111', 'Homework', 'HW', 20, 0.1000, 2),
  ('11111111-1111-1111-1111-111111111111', 'Tests', 'TEST', 30, 0.3000, 3),
  ('11111111-1111-1111-1111-111111111111', 'Group activities', 'GROUP', 20, 0.1000, 4),
  ('11111111-1111-1111-1111-111111111111', 'Examinations', 'EXAM', 100, 0.4000, 5);

-- Phase 2: grading bands for school 1 (illustrative school-default bands)
insert into public.grading_bands
  (school_id, grading_policy_id, letter, descriptor, min_percentage, is_pass, comment_hint, ordering)
values
  ('11111111-1111-1111-1111-111111111111', '14141414-1414-1414-1414-141414141401', 'A', 'Excellent', 80.00, true, 'Outstanding consistent performance.', 1),
  ('11111111-1111-1111-1111-111111111111', '14141414-1414-1414-1414-141414141401', 'B', 'Very good', 70.00, true, 'Strong performance; keep it up.', 2),
  ('11111111-1111-1111-1111-111111111111', '14141414-1414-1414-1414-141414141401', 'C', 'Good', 60.00, true, 'Satisfactory; room to grow.', 3),
  ('11111111-1111-1111-1111-111111111111', '14141414-1414-1414-1414-141414141401', 'D', 'Satisfactory', 50.00, true, 'Meets minimum expectations.', 4),
  ('11111111-1111-1111-1111-111111111111', '14141414-1414-1414-1414-141414141401', 'F', 'Needs improvement', 0.00, false, 'Requires targeted support.', 5);

-- Phase 2: onboarding state (school 1 already configured in seed → mark complete)
insert into public.school_onboarding (school_id, current_step, steps, completed_at)
values
  (
    '11111111-1111-1111-1111-111111111111',
    'review',
    '{"identity":"complete","calendar":"complete","curriculum":"complete","grading":"complete","review":"complete"}'::jsonb,
    timezone('utc', now())
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'calendar',
    '{"identity":"complete","calendar":"pending"}'::jsonb,
    null
  );

-- Phase 2: a default report layout draft per school
insert into public.report_layouts (school_id, name, level, configuration_json, is_default)
values
  (
    '11111111-1111-1111-1111-111111111111',
    'Standard report card',
    null,
    '{"header":{"show_logo":true,"show_address":true,"show_contact":true},"sections":["student","academic","behavior","attendance","comments","signatures"],"columns":["subject","total","max","percentage","grade","comment"],"show_behavior":true,"show_attendance":true,"show_ranking":true}'::jsonb,
    true
  ),
  (
    '22222222-2222-2222-2222-222222222222',
    'Standard report card',
    null,
    '{"header":{"show_logo":true,"show_address":true,"show_contact":true},"sections":["student","academic","behavior","attendance","comments","signatures"],"columns":["subject","total","max","percentage","grade","comment"],"show_behavior":false,"show_attendance":true,"show_ranking":false}'::jsonb,
    true
  );