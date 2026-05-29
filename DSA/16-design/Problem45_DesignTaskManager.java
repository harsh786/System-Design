import java.util.*;

/**
 * Problem 45: Design Task Manager
 * 
 * API Contract:
 * - add(userId, taskId, priority): Add task
 * - edit(taskId, newPriority): Change task priority
 * - rmv(taskId): Remove task
 * - execTop(): Execute and remove highest priority task (highest taskId on tie). Return userId.
 * 
 * Complexity: add/edit/rmv O(log n), execTop O(log n)
 * Data Structure: TreeSet sorted by (priority desc, taskId desc) + HashMap for lookup
 * 
 * Production Analogy: OS process scheduler, job queue with priorities,
 * Kubernetes pod scheduling, CI/CD pipeline prioritization
 */
public class Problem45_DesignTaskManager {

    static class TaskManager {
        private int[] taskUser;     // taskId -> userId (sparse, using map)
        private Map<Integer, Integer> taskToPriority;
        private Map<Integer, Integer> taskToUser;
        private TreeSet<int[]> pq; // [priority, taskId]

        public TaskManager(List<List<Integer>> tasks) {
            taskToPriority = new HashMap<>();
            taskToUser = new HashMap<>();
            pq = new TreeSet<>((a, b) -> a[0] != b[0] ? b[0] - a[0] : b[1] - a[1]);
            for (List<Integer> t : tasks) add(t.get(0), t.get(1), t.get(2));
        }

        public void add(int userId, int taskId, int priority) {
            taskToUser.put(taskId, userId);
            taskToPriority.put(taskId, priority);
            pq.add(new int[]{priority, taskId});
        }

        public void edit(int taskId, int newPriority) {
            int oldPri = taskToPriority.get(taskId);
            pq.remove(new int[]{oldPri, taskId});
            taskToPriority.put(taskId, newPriority);
            pq.add(new int[]{newPriority, taskId});
        }

        public void rmv(int taskId) {
            int pri = taskToPriority.get(taskId);
            pq.remove(new int[]{pri, taskId});
            taskToPriority.remove(taskId);
            taskToUser.remove(taskId);
        }

        public int execTop() {
            int[] top = pq.pollFirst();
            int taskId = top[1];
            int userId = taskToUser.get(taskId);
            taskToPriority.remove(taskId);
            taskToUser.remove(taskId);
            return userId;
        }
    }

    public static void main(String[] args) {
        List<List<Integer>> tasks = Arrays.asList(
            Arrays.asList(1, 101, 10),
            Arrays.asList(2, 102, 20),
            Arrays.asList(3, 103, 15)
        );
        TaskManager tm = new TaskManager(tasks);
        assert tm.execTop() == 2;  // task 102, priority 20
        tm.edit(103, 25);
        assert tm.execTop() == 3;  // task 103, priority 25 now
        tm.add(4, 104, 5);
        tm.rmv(101);
        assert tm.execTop() == 4;  // only task 104 left

        System.out.println("All tests passed!");
    }
}
