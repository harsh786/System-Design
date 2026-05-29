import java.util.*;

public class Problem46_ServerCapacityPlanning {
    public int minServers(int[][] tasks, int serverCapacity) {
        TreeMap<Integer, Integer> sweep = new TreeMap<>();
        for (int[] t : tasks) { sweep.merge(t[0], t[2], Integer::sum); sweep.merge(t[1], -t[2], Integer::sum); }
        int maxLoad = 0, cur = 0;
        for (int v : sweep.values()) { cur += v; maxLoad = Math.max(maxLoad, cur); }
        return (maxLoad + serverCapacity - 1) / serverCapacity;
    }

    public static void main(String[] args) {
        Problem46_ServerCapacityPlanning sol = new Problem46_ServerCapacityPlanning();
        // [start, end, load]
        System.out.println(sol.minServers(new int[][]{{0,10,50},{5,15,80},{10,20,60}}, 100)); // 2
    }
}
