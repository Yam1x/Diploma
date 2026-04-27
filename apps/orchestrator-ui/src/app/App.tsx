import { Route, Routes } from "react-router-dom";

import { Layout } from "../components/Layout";
import { MinioFilesPage } from "../pages/MinioFiles";
import { EventRuleDetailsPage } from "../pages/EventRuleDetails";
import { EventRuleFormPage } from "../pages/EventRuleForm";
import { EventRulesListPage } from "../pages/EventRulesList";
import { RecoveryRuleDetailsPage } from "../pages/RecoveryRuleDetails";
import { RecoveryRuleFormPage } from "../pages/RecoveryRuleForm";
import { RecoveryRulesListPage } from "../pages/RecoveryRulesList";
import { TaskDetailsPage } from "../pages/TaskDetails";
import { TaskFormPage } from "../pages/TaskForm";
import { TasksListPage } from "../pages/TasksList";
import { TaskTypeSelectPage } from "../pages/TaskTypeSelect";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<TasksListPage />} />
        <Route path="/event-rules" element={<EventRulesListPage />} />
        <Route path="/event-rules/new" element={<EventRuleFormPage />} />
        <Route path="/event-rules/:ruleId" element={<EventRuleDetailsPage />} />
        <Route path="/event-rules/:ruleId/edit" element={<EventRuleFormPage />} />
        <Route path="/recovery-rules" element={<RecoveryRulesListPage />} />
        <Route path="/recovery-rules/new" element={<RecoveryRuleFormPage />} />
        <Route path="/recovery-rules/:ruleId" element={<RecoveryRuleDetailsPage />} />
        <Route path="/recovery-rules/:ruleId/edit" element={<RecoveryRuleFormPage />} />
        <Route path="/tasks/new" element={<TaskTypeSelectPage />} />
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailsPage />} />
        <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
        <Route path="/minio-files" element={<MinioFilesPage />} />
      </Routes>
    </Layout>
  );
}
