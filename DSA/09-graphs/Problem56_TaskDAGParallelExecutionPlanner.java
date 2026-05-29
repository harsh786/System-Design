import java.util.*;

/**
 * Problem 56: Task DAG Parallel Execution Planner
 * 
 * Production Relevance:
 * - CI/CD pipelines (GitHub Actions, GitLab CI): maximize parallelism respecting dependencies
 * - Apache Airflow DAGs, Spark stage scheduling, build systems (Bazel)
 * - Reduces wall-clock time by running independent tasks in parallel
 * - Critical for large-scale ML training pipelines, ETL workflows
 * 
 * Architect Considerations:
 * - Resource constraints limit actual parallelism (e.g., max 4 concurrent jobs)
 * - Task duration awareness for optimal scheduling (critical path method)
 * - Dynamic DAGs: tasks may spawn sub-tasks at runtime
 */
public class Problem56_TaskDAGParallelExecutionPlanner {

    static class Task {
        String id;
        int durationMs;
        List<String> dependencies;

        Task(String id, int durationMs, String... deps) {
            this.id = id; this.durationMs = durationMs;
            this.dependencies = Arrays.asList(deps);
        }
    }

    static class ExecutionPlan {
        List<List<String>> waves; // each wave runs in parallel
        int totalWallClockMs;
        int totalSequentialMs;
        double speedup;

        @Override
        public String toString() {
            StringBuilder sb = new StringBuilder();
            for (int i = 0; i < waves.size(); i++) {
                sb.append(String.format("  Wave %d: %s%n", i + 1, waves.get(i)));
            }
            sb.append(String.format("  Wall clock: %dms (sequential: %dms, speedup: %.2fx)", totalWallClockMs, totalSequentialMs, speedup));
            return sb.toString();
        }
    }

    static class DAGScheduler {
        Map<String, Task> tasks = new LinkedHashMap<>();

        void addTask(Task task) { tasks.put(task.id, task); }

        // Compute parallel waves using topological level assignment
        ExecutionPlan plan() {
            Map<String, Integer> inDeg = new HashMap<>();
            Map<String, Set<String>> adj = new HashMap<>();
            tasks.keySet().forEach(t -> { inDeg.put(t, 0); adj.put(t, new HashSet<>()); });

            for (Task t : tasks.values()) {
                for (String dep : t.dependencies) {
                    adj.get(dep).add(t.id);
                    inDeg.merge(t.id, 1, Integer::sum);
                }
            }

            ExecutionPlan plan = new ExecutionPlan();
            plan.waves = new ArrayList<>();
            Set<String> completed = new HashSet<>();
            int wallClock = 0;
            int sequential = tasks.values().stream().mapToInt(t -> t.durationMs).sum();

            while (completed.size() < tasks.size()) {
                // Find all tasks with met dependencies
                List<String> wave = new ArrayList<>();
                for (String t : tasks.keySet()) {
                    if (!completed.contains(t) && inDeg.get(t) == 0) wave.add(t);
                }
                if (wave.isEmpty()) break; // cycle

                plan.waves.add(wave);
                int waveDuration = wave.stream().mapToInt(t -> tasks.get(t).durationMs).max().orElse(0);
                wallClock += waveDuration;

                for (String t : wave) {
                    completed.add(t);
                    for (String next : adj.get(t)) {
                        inDeg.merge(next, -1, Integer::sum);
                    }
                }
            }

            plan.totalWallClockMs = wallClock;
            plan.totalSequentialMs = sequential;
            plan.speedup = (double) sequential / wallClock;
            return plan;
        }

        // Critical path: longest path through DAG (determines minimum wall-clock)
        List<String> criticalPath() {
            Map<String, Integer> earliest = new HashMap<>();
            Map<String, String> prev = new HashMap<>();
            tasks.keySet().forEach(t -> earliest.put(t, 0));

            // Process in topological order
            List<String> topo = topoSort();
            for (String t : topo) {
                int finish = earliest.get(t) + tasks.get(t).durationMs;
                for (Task task : tasks.values()) {
                    if (task.dependencies.contains(t)) {
                        if (finish > earliest.get(task.id)) {
                            earliest.put(task.id, finish);
                            prev.put(task.id, t);
                        }
                    }
                }
            }

            // Find task with latest finish
            String last = topo.get(0);
            for (String t : topo) {
                if (earliest.get(t) + tasks.get(t).durationMs > earliest.get(last) + tasks.get(last).durationMs) last = t;
            }

            List<String> path = new ArrayList<>();
            for (String at = last; at != null; at = prev.get(at)) path.add(at);
            Collections.reverse(path);
            return path;
        }

        private List<String> topoSort() {
            Map<String, Integer> inDeg = new HashMap<>();
            tasks.keySet().forEach(t -> inDeg.put(t, 0));
            for (Task t : tasks.values()) for (String d : t.dependencies) inDeg.merge(t.id, 1, Integer::sum);
            Queue<String> q = new LinkedList<>();
            inDeg.forEach((t, d) -> { if (d == 0) q.offer(t); });
            List<String> order = new ArrayList<>();
            while (!q.isEmpty()) {
                String u = q.poll(); order.add(u);
                for (Task t : tasks.values()) {
                    if (t.dependencies.contains(u) && inDeg.merge(t.id, -1, Integer::sum) == 0) q.offer(t.id);
                }
            }
            return order;
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Task DAG Parallel Execution Planner ===\n");

        DAGScheduler scheduler = new DAGScheduler();
        scheduler.addTask(new Task("checkout", 5));
        scheduler.addTask(new Task("install-deps", 30, "checkout"));
        scheduler.addTask(new Task("lint", 10, "install-deps"));
        scheduler.addTask(new Task("unit-tests", 60, "install-deps"));
        scheduler.addTask(new Task("build", 45, "install-deps"));
        scheduler.addTask(new Task("integration-tests", 90, "build"));
        scheduler.addTask(new Task("docker-build", 30, "build"));
        scheduler.addTask(new Task("deploy-staging", 20, "docker-build", "integration-tests", "lint", "unit-tests"));

        ExecutionPlan plan = scheduler.plan();
        System.out.println("Execution Plan:");
        System.out.println(plan);
        System.out.println("\nCritical path: " + scheduler.criticalPath());
    }
}
