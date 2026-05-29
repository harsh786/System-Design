import java.util.*;

/**
 * Problem 57: Priority Aging to Prevent Starvation
 * 
 * Production Relevance:
 * - Fixed-priority scheduling can starve low-priority tasks indefinitely
 * - Aging: gradually increase priority of waiting tasks over time
 * - Used in OS schedulers, database query queues, work-stealing thread pools
 * - Guarantees bounded wait time for all priority levels
 * 
 * Architect Considerations:
 * - Aging rate: how fast does priority increase per unit of wait time
 * - Priority ceiling: aged tasks shouldn't exceed certain priority level
 * - Reset on execution: priority resets to base after task gets CPU time
 */
public class Problem57_PriorityAgingPreventStarvation {

    static class AgingTask {
        String id;
        int basePriority; // 1=highest, 10=lowest
        int currentPriority;
        long enqueueTime;
        long lastBoostTime;
        int executionCount;

        AgingTask(String id, int priority, long enqueueTime) {
            this.id = id; this.basePriority = priority;
            this.currentPriority = priority; this.enqueueTime = enqueueTime;
            this.lastBoostTime = enqueueTime;
        }

        double effectivePriority() { return currentPriority; }
    }

    static class AgingPriorityQueue {
        private final List<AgingTask> tasks = new ArrayList<>();
        private final int agingInterval; // ms between aging boosts
        private final int agingAmount;   // priority boost per interval
        private final int priorityCeiling; // don't age beyond this
        private long currentTime = 0;
        private final List<String> log = new ArrayList<>();

        AgingPriorityQueue(int agingInterval, int agingAmount, int priorityCeiling) {
            this.agingInterval = agingInterval;
            this.agingAmount = agingAmount;
            this.priorityCeiling = priorityCeiling;
        }

        void enqueue(AgingTask task) { tasks.add(task); }

        void advanceTime(long newTime) {
            currentTime = newTime;
            // Apply aging to all waiting tasks
            for (AgingTask task : tasks) {
                long waitTime = currentTime - task.lastBoostTime;
                int boosts = (int) (waitTime / agingInterval);
                if (boosts > 0) {
                    int oldPriority = task.currentPriority;
                    task.currentPriority = Math.max(priorityCeiling, task.currentPriority - boosts * agingAmount);
                    task.lastBoostTime = currentTime;
                    if (oldPriority != task.currentPriority) {
                        log.add(String.format("  t=%d: %s aged %d->%d (waited %dms)",
                                currentTime, task.id, oldPriority, task.currentPriority, currentTime - task.enqueueTime));
                    }
                }
            }
        }

        AgingTask dequeue() {
            if (tasks.isEmpty()) return null;
            tasks.sort(Comparator.comparingDouble(AgingTask::effectivePriority));
            AgingTask best = tasks.remove(0);
            best.executionCount++;
            // Reset priority on execution
            best.currentPriority = best.basePriority;
            best.lastBoostTime = currentTime;
            return best;
        }

        int size() { return tasks.size(); }
        void printLog() { log.forEach(System.out::println); }
    }

    public static void main(String[] args) {
        System.out.println("=== Priority Aging to Prevent Starvation ===\n");

        // Age by 1 priority level every 100ms, ceiling at priority 2
        AgingPriorityQueue queue = new AgingPriorityQueue(100, 1, 2);

        // High priority tasks keep arriving, starving low priority
        queue.enqueue(new AgingTask("low-task-1", 8, 0));
        queue.enqueue(new AgingTask("low-task-2", 9, 0));
        queue.enqueue(new AgingTask("high-task-1", 2, 50));
        queue.enqueue(new AgingTask("high-task-2", 1, 100));
        queue.enqueue(new AgingTask("med-task-1", 5, 150));

        System.out.println("Without aging, low tasks would never execute.\nWith aging:");

        // Simulate time passing with periodic dequeues
        for (int t = 200; t <= 1000; t += 200) {
            queue.advanceTime(t);
            AgingTask task = queue.dequeue();
            if (task != null) {
                System.out.printf("  t=%d: Execute %s (base=%d, aged=%d)%n",
                        t, task.id, task.basePriority, task.currentPriority);
                // Re-enqueue (simulate recurring tasks)
                task.enqueueTime = t;
                queue.enqueue(task);
            }
        }

        System.out.println("\nAging log:");
        queue.printLog();
    }
}
