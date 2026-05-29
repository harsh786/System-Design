import java.util.*;

public class Problem50_TrafficFlowAnalysis {
    public int[] trafficFlow(int[][] vehicles, int maxTime) {
        int[] diff = new int[maxTime + 2];
        for (int[] v : vehicles) { diff[v[0]]++; if (v[1] + 1 <= maxTime) diff[v[1] + 1]--; }
        int[] flow = new int[maxTime + 1];
        flow[0] = diff[0];
        for (int i = 1; i <= maxTime; i++) flow[i] = flow[i-1] + diff[i];
        return flow;
    }

    public int peakHour(int[][] vehicles, int maxTime) {
        int[] flow = trafficFlow(vehicles, maxTime);
        int max = 0, peak = 0;
        for (int i = 0; i <= maxTime; i++) { if (flow[i] > max) { max = flow[i]; peak = i; } }
        return peak;
    }

    public static void main(String[] args) {
        Problem50_TrafficFlowAnalysis sol = new Problem50_TrafficFlowAnalysis();
        int[][] vehicles = {{0,5},{2,8},{4,10},{6,12},{8,14}};
        System.out.println("Peak hour: " + sol.peakHour(vehicles, 15));
        System.out.println("Flow: " + Arrays.toString(sol.trafficFlow(vehicles, 15)));
    }
}
