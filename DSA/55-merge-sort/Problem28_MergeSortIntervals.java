import java.util.*;

public class Problem28_MergeSortIntervals {
    static int[][] mergeIntervals(int[][] intervals) {
        Arrays.sort(intervals, (a, b) -> a[0] - b[0]); // merge sort based
        List<int[]> merged = new ArrayList<>();
        for (int[] interval : intervals) {
            if (merged.isEmpty() || merged.get(merged.size()-1)[1] < interval[0])
                merged.add(interval);
            else merged.get(merged.size()-1)[1] = Math.max(merged.get(merged.size()-1)[1], interval[1]);
        }
        return merged.toArray(new int[0][]);
    }
    
    public static void main(String[] args) {
        int[][] intervals = {{1,3},{2,6},{8,10},{15,18}};
        for (int[] i : mergeIntervals(intervals)) System.out.println(Arrays.toString(i));
    }
}
