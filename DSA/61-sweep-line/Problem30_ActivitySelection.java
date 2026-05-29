import java.util.*;

public class Problem30_ActivitySelection {
    public List<int[]> selectActivities(int[][] activities) {
        Arrays.sort(activities, (a, b) -> a[1] - b[1]);
        List<int[]> selected = new ArrayList<>();
        int lastEnd = -1;
        for (int[] act : activities) {
            if (act[0] >= lastEnd) { selected.add(act); lastEnd = act[1]; }
        }
        return selected;
    }

    public static void main(String[] args) {
        Problem30_ActivitySelection sol = new Problem30_ActivitySelection();
        List<int[]> res = sol.selectActivities(new int[][]{{1,2},{3,4},{0,6},{5,7},{8,9},{5,9}});
        for (int[] a : res) System.out.println(Arrays.toString(a));
    }
}
