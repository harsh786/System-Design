import java.util.*;

/**
 * Problem 59: Hierarchical Priority Queue
 * 
 * Production Relevance:
 * - Multi-level priority: project > team > individual request priority
 * - Used in cloud resource allocation (org > project > workload), ISP traffic shaping
 * - Kubernetes: namespace resource quotas with priority classes
 * - Hierarchical fair sharing: parent's share divided among children
 * 
 * Architect Considerations:
 * - Tree of queues: each node has a share of parent's capacity
 * - DRF (Dominant Resource Fairness) for multi-resource allocation
 * - Preemption: higher-level priority can preempt lower-level tasks
 */
public class Problem59_HierarchicalPriorityQueue {

    static class QueueNode {
        String name;
        int weight; // share relative to siblings
        PriorityQueue<Task> localQueue = new PriorityQueue<>(Comparator.comparingInt(t -> t.priority));
        List<QueueNode> children = new ArrayList<>();
        QueueNode parent;
        int totalServed = 0;

        QueueNode(String name, int weight) { this.name = name; this.weight = weight; }

        void addChild(QueueNode child) { child.parent = this; children.add(child); }
    }

    static class Task {
        String id;
        int priority;
        String queuePath;

        Task(String id, int priority) { this.id = id; this.priority = priority; }
    }

    static class HierarchicalScheduler {
        QueueNode root;
        Map<String, QueueNode> queueMap = new LinkedHashMap<>();

        HierarchicalScheduler(QueueNode root) {
            this.root = root;
            indexQueues(root, "");
        }

        private void indexQueues(QueueNode node, String path) {
            String fullPath = path.isEmpty() ? node.name : path + "/" + node.name;
            queueMap.put(fullPath, node);
            for (QueueNode child : node.children) indexQueues(child, fullPath);
        }

        void submit(String queuePath, Task task) {
            QueueNode queue = queueMap.get(queuePath);
            if (queue != null) {
                task.queuePath = queuePath;
                queue.localQueue.offer(task);
            }
        }

        // Schedule next task respecting hierarchy
        Task schedule() {
            return scheduleFrom(root);
        }

        private Task scheduleFrom(QueueNode node) {
            // If leaf with tasks, return highest priority task
            if (node.children.isEmpty()) {
                Task t = node.localQueue.poll();
                if (t != null) node.totalServed++;
                return t;
            }

            // Select child based on weighted fair share (least served relative to weight)
            List<QueueNode> activeChildren = new ArrayList<>();
            for (QueueNode child : node.children) {
                if (hasWork(child)) activeChildren.add(child);
            }
            if (activeChildren.isEmpty()) return null;

            // Pick child with lowest (served/weight) ratio
            activeChildren.sort(Comparator.comparingDouble(c ->
                    (double) c.totalServed / c.weight));
            QueueNode selected = activeChildren.get(0);
            Task t = scheduleFrom(selected);
            if (t != null) selected.totalServed++;
            return t;
        }

        private boolean hasWork(QueueNode node) {
            if (!node.localQueue.isEmpty()) return true;
            for (QueueNode child : node.children) {
                if (hasWork(child)) return true;
            }
            return false;
        }

        void printStats() {
            System.out.println("\nFairness stats:");
            queueMap.forEach((path, node) -> {
                if (!node.children.isEmpty() || node.totalServed > 0)
                    System.out.printf("  %-25s weight=%d served=%d%n", path, node.weight, node.totalServed);
            });
        }
    }

    public static void main(String[] args) {
        System.out.println("=== Hierarchical Priority Queue ===\n");

        // root -> [engineering(weight=5), analytics(weight=3), ops(weight=2)]
        QueueNode root = new QueueNode("root", 1);
        QueueNode eng = new QueueNode("engineering", 5);
        QueueNode analytics = new QueueNode("analytics", 3);
        QueueNode ops = new QueueNode("ops", 2);
        root.addChild(eng); root.addChild(analytics); root.addChild(ops);

        // engineering -> [backend(3), frontend(2)]
        QueueNode backend = new QueueNode("backend", 3);
        QueueNode frontend = new QueueNode("frontend", 2);
        eng.addChild(backend); eng.addChild(frontend);

        HierarchicalScheduler scheduler = new HierarchicalScheduler(root);

        // Submit tasks to various queues
        for (int i = 0; i < 10; i++) scheduler.submit("root/engineering/backend", new Task("be-" + i, i));
        for (int i = 0; i < 10; i++) scheduler.submit("root/engineering/frontend", new Task("fe-" + i, i));
        for (int i = 0; i < 10; i++) scheduler.submit("root/analytics", new Task("an-" + i, i));
        for (int i = 0; i < 10; i++) scheduler.submit("root/ops", new Task("ops-" + i, i));

        // Schedule 20 tasks and observe fair distribution
        System.out.println("Scheduling 20 tasks:");
        for (int i = 0; i < 20; i++) {
            Task t = scheduler.schedule();
            if (t != null) System.out.printf("  %2d: %s (from %s)%n", i + 1, t.id, t.queuePath);
        }

        scheduler.printStats();
    }
}
