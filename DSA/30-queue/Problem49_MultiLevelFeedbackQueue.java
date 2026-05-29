import java.util.*;

public class Problem49_MultiLevelFeedbackQueue {
    static class Process { String name; int burstTime; Process(String n, int b) { name = n; burstTime = b; } }
    static class MLFQ {
        Queue<Process>[] queues;
        int[] timeQuantums;
        @SuppressWarnings("unchecked")
        MLFQ(int levels, int[] quantums) {
            queues = new LinkedList[levels]; timeQuantums = quantums;
            for (int i = 0; i < levels; i++) queues[i] = new LinkedList<>();
        }
        void addProcess(Process p) { queues[0].offer(p); }
        void schedule() {
            for (int i = 0; i < queues.length; i++) {
                while (!queues[i].isEmpty()) {
                    Process p = queues[i].poll();
                    int quantum = timeQuantums[i];
                    if (p.burstTime <= quantum) {
                        System.out.println("Level " + i + ": " + p.name + " completes (burst=" + p.burstTime + ")");
                    } else {
                        p.burstTime -= quantum;
                        System.out.println("Level " + i + ": " + p.name + " runs " + quantum + "ms, remaining=" + p.burstTime);
                        if (i + 1 < queues.length) queues[i + 1].offer(p); else queues[i].offer(p);
                    }
                }
            }
        }
    }
    public static void main(String[] args) {
        MLFQ mlfq = new MLFQ(3, new int[]{4, 8, 16});
        mlfq.addProcess(new Process("P1", 20));
        mlfq.addProcess(new Process("P2", 3));
        mlfq.addProcess(new Process("P3", 10));
        mlfq.schedule();
    }
}
