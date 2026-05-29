import java.util.*;

/**
 * Problem 52: Deadline-Aware Task Scheduler
 * 
 * Production Relevance:
 * - Real-time systems: tasks must complete before deadline or SLA is violated
 * - Earliest Deadline First (EDF): optimal for single processor real-time scheduling
 * - Used in network packet scheduling (QoS), message broker TTL, job schedulers
 * - Trade-off: admitting too many tasks causes deadline misses for all
 * 
 * Architect Considerations:
 * - Admission control: reject tasks that can't meet deadline given current load
 * - Slack-based scheduling: schedule tasks with least slack (deadline - remaining work)
 * - Overload handling: which tasks to shed when capacity < demand
 */
public class Problem52_DeadlineAwareTaskScheduler {

    static class DeadlineTask {
        String id;
        int processingTime;
        long deadline;
        long arrivalTime;
        long startTime = -1;
        long completionTime = -1;

        DeadlineTask(String id, int processingTime, long deadline, long arrivalTime) {
            this.id = id; this.processingTime = processingTime;
            this.deadline = deadline; this.arrivalTime = arrivalTime;
        }

        long slack(long currentTime) { return deadline - currentTime - processingTime; }
        boolean metDeadline() { return completionTime <= deadline; }
    }

    static class EDFScheduler {
        PriorityQueue<DeadlineTask> readyQueue = new PriorityQueue<>(
                Comparator.comparingLong(t -> t.deadline));
        List<DeadlineTask> completed = new ArrayList<>();
        List<DeadlineTask> rejected = new ArrayList<>();
        long currentTime = 0;

        // Admission control: can we guarantee deadline if we admit this task?
        boolean admit(DeadlineTask task) {
            // Check if adding this task would cause any admitted task to miss deadline
            long simulatedTime = currentTime;
            List<DeadlineTask> allTasks = new ArrayList<>(readyQueue);
            allTasks.add(task);
            allTasks.sort(Comparator.comparingLong(t -> t.deadline));

            for (DeadlineTask t : allTasks) {
                simulatedTime += t.processingTime;
                if (simulatedTime > t.deadline) return false;
            }
            return true;
        }

        void submit(DeadlineTask task) {
            if (admit(task)) {
                readyQueue.offer(task);
            } else {
                rejected.add(task);
            }
        }

        void run() {
            while (!readyQueue.isEmpty()) {
                DeadlineTask task = readyQueue.poll();
                task.startTime = currentTime;
                currentTime += task.processingTime;
                task.completionTime = currentTime;
                completed.add(task);
            }
        }

        void printResults() {
            System.out.println("Completed tasks:");
            for (DeadlineTask t : completed) {
                System.out.printf("  %s: deadline=%d, completed=%d %s%n",
                        t.id, t.deadline, t.completionTime,
                        t.metDeadline() ? "✓ ON TIME" : "✗ LATE");
            }
            if (!rejected.isEmpty()) {
                System.out.println("Rejected (would miss deadline):");
                rejected.forEach(t -> System.out.printf("  %s: need %d by %d%n", t.id, t.processingTime, t.deadline));
            }
            long onTime = completed.stream().filter(DeadlineTask::metDeadline).count();
            System.out.printf("SLA: %d/%d tasks met deadline (%.0f%%)%n",
                    onTime, completed.size(), 100.0 * onTime / Math.max(1, completed.size()));
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Deadline-Aware Task Scheduler (EDF) ===\n");

        EDFScheduler scheduler = new EDFScheduler();
        scheduler.submit(new DeadlineTask("api-response", 3, 10, 0));
        scheduler.submit(new DeadlineTask("db-query", 5, 8, 0));
        scheduler.submit(new DeadlineTask("batch-export", 10, 25, 0));
        scheduler.submit(new DeadlineTask("urgent-alert", 2, 5, 0));
        scheduler.submit(new DeadlineTask("impossible-task", 20, 12, 0)); // Should be rejected

        scheduler.run();
        scheduler.printResults();
    }
}
