import { Route, Routes } from "react-router-dom";

import { Layout } from "../components/Layout";
import { MinioFilesPage } from "../pages/MinioFiles";
import { TaskDetailsPage } from "../pages/TaskDetails";
import { TaskFormPage } from "../pages/TaskForm";
import { TasksListPage } from "../pages/TasksList";
import { TaskTypeSelectPage } from "../pages/TaskTypeSelect";

export function App() {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<TasksListPage />} />
        <Route path="/tasks/new" element={<TaskTypeSelectPage />} />
        <Route path="/tasks/new/:taskType" element={<TaskFormPage />} />
        <Route path="/tasks/:taskId" element={<TaskDetailsPage />} />
        <Route path="/tasks/:taskId/edit" element={<TaskFormPage />} />
        <Route path="/minio-files" element={<MinioFilesPage />} />
      </Routes>
    </Layout>
  );
}
