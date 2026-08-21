import type { WorkerOptions, WorkerState } from "./contracts.ts";

export const MAX_REPAIR_READ_HANDOFFS = 1;

interface RepairReadHandoffState {
	readPaths: Set<string>;
	repairReadHandoffs: number;
}

export function allowsRepairReadHandoff(
	options: Pick<WorkerOptions, "mode">,
	requiredTool: string,
	requestedTool: string,
	repairSources: readonly string[],
	state: RepairReadHandoffState,
): boolean {
	return options.mode === "repair"
		&& requiredTool === "write_expected_output"
		&& requestedTool === "read_repair_target"
		&& repairSources.length > 0
		&& repairSources.every((path) => state.readPaths.has(path))
		&& state.repairReadHandoffs < MAX_REPAIR_READ_HANDOFFS;
}

export function completeRepairReadHandoff(
	state: Pick<WorkerState, "repairReadHandoffs">,
): { status: "read_phase_complete"; next_tool: "write_expected_output"; returned: 0 } {
	if (state.repairReadHandoffs >= MAX_REPAIR_READ_HANDOFFS) {
		throw new Error("repair read phase is already complete; call write_expected_output");
	}
	state.repairReadHandoffs += 1;
	return {
		status: "read_phase_complete",
		next_tool: "write_expected_output",
		returned: 0,
	};
}
