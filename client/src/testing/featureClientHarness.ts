import { createAdvisorClient } from "@/features/advisor/services/advisorClient";
import { createDeliveryClient } from "@/features/delivery/services/deliveryClient";
import { createOrreryClient } from "@/features/orrery/services/orreryClient";
import { createProjectsClient } from "@/features/projects/services/projectsClient";
import { createQualityClient } from "@/features/quality/services/qualityClient";
import { createSettingsClient } from "@/features/settings/services/settingsClient";
import { createWorkflowClient } from "@/features/workflow/services/workflowClient";
import { MockFeatureTransport } from "./mockFeatureTransport";

export function createFeatureClientHarness() {
  const transport = new MockFeatureTransport();
  return {
    transport,
    clients: {
      advisor: createAdvisorClient(transport),
      delivery: createDeliveryClient(transport),
      orrery: createOrreryClient(transport),
      projects: createProjectsClient(transport),
      quality: createQualityClient(transport),
      settings: createSettingsClient(transport, async () => undefined),
      workflow: createWorkflowClient(transport),
    },
  };
}
