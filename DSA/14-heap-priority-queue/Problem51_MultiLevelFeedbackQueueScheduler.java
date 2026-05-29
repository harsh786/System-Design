import java.util.*;

/**
 * Problem 51: Multi-Level Feedback Queue Scheduler
 * 
 * Production Relevance:
 * - OS CPU scheduling (Linux CFS, Windows): processes move between priority queues
 * - Short tasks get high priority (interactive), long tasks demoted (batch)
 * - Used in database query schedulers, thread pool task scheduling
 * - Prevents starvation while favoring latency-sensitive workloads
 * 
 * Architect Considerations:
 * - Multiple queues with different time quanta (short quantum at top, long at bottom)
 * - Promotion rules prevent starvation of long-running tasks
 * - Real-time priority levels may preempt all lower levels
 */
public class Problem51_MultiLevelFeedbackQueueScheduler {

    static class Task {
        String id;
        int remainingTime;
        int totalTime;
        int currentLevel;
        int waitTime;

        Task(String id, int totalTime) {
            this.id = id; this.totalTime = totalTime; this.remainingTime = totalTime;
        }

        @Override
        public String toString() { return String.format("%s(rem=%d,level=%d)", id, remainingTime, currentLevel); }
    }

    static class MLFQScheduler {
        private final int numLevels;
        private final int[] timeQuanta; // time quantum per level
        private final List<Queue<Task>> queues;
        private final int boostInterval; // promote all tasks to top after N ticks
        private int tickCount = 0;
        private final List<String> schedule = new ArrayList<>();

        MLFQScheduler(int numLevels, int[] timeQuanta, int boostInterval) {
            this.numLevels = numLevels;
            this.timeQuanta = timeQuanta;
            this.boostInterval = boostInterval;
            this.queues = new ArrayList<>();
            for (int i = 0; i < numLevels; i++) queues.add(new LinkedList<>());
        }

        void addTask(Task task) {
            task.currentLevel = 0; // Start at highest priority
            queues.get(0).offer(task);
        }

        void run(int totalTicks) {
            for (int tick = 0; tick < totalTicks; tick++) {
                tickCount++;

                // Priority boost: move all tasks to top queue periodically
                if (tickCount % boostInterval == 0) {
                    for (int i = 1; i < numLevels; i++) {
                        while (!queues.get(i).isEmpty()) {
                            Task t = queues.get(i).poll();
                            t.currentLevel = 0;
                            queues.get(0).offer(t);
                        }
                    }
                    schedule.add("[BOOST]");
                }

                // Find highest priority non-empty queue
                Task current = null;
                for (int level = 0; level < numLevels; level++) {
                    if (!queues.get(level).isEmpty()) {
                        current = queues.get(level).poll();
                        break;
                    }
                }

                if (current == null) { schedule.add("IDLE"); continue; }

                // Execute for time quantum of current level
                int quantum = timeQuanta[current.currentLevel];
                int executed = Math.min(quantum, current.remainingTime);
                current.remainingTime -= executed;
                tick += executed - 1; // Advance tick by quantum

                if (current.remainingTime <= 0) {
                    schedule.add(String.format("t=%d: %s COMPLETED", tickCount, current.id));
                } else {
                    // Demote to next level (used full quantum without completing)
                    int nextLevel = Math.min(current.currentLevel + 1, numLevels - 1);
                    current.currentLevel = nextLevel;
                    queues.get(nextLevel).offer(current);
                    schedule.add(String.format("t=%d: %s ran %dms, demoted to L%d",
                            tickCount, current.id, executed, nextLevel));
                }
            }
        }

        void printSchedule() { schedule.forEach(System.out::println); }
    }

    public static void main(String[] args) {
        System.out.println("=== Multi-Level Feedback Queue Scheduler ===\n");

        // 3 levels: quantum 2, 4, 8; boost every 20 ticks
        MLFQScheduler scheduler = new MLFQScheduler(3, new int[]{2, 4, 8}, 20);

        scheduler.addTask(new Task("interactive", 3));  // Short task
        scheduler.addTask(new Task("batch-job", 15));   // Long task
        scheduler.addTask(new Task("api-handler", 4));  // Medium task

        scheduler.run(30);
        scheduler.printSchedule();
    }
}
