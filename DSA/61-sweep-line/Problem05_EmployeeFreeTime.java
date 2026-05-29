import java.util.*;

public class Problem05_EmployeeFreeTime {
    public List<int[]> employeeFreeTime(List<List<int[]>> schedule) {
        List<int[]> all = new ArrayList<>();
        for (List<int[]> emp : schedule) all.addAll(emp);
        all.sort((a, b) -> a[0] - b[0]);
        List<int[]> res = new ArrayList<>();
        int end = all.get(0)[1];
        for (int i = 1; i < all.size(); i++) {
            if (all.get(i)[0] > end) res.add(new int[]{end, all.get(i)[0]});
            end = Math.max(end, all.get(i)[1]);
        }
        return res;
    }

    public static void main(String[] args) {
        Problem05_EmployeeFreeTime sol = new Problem05_EmployeeFreeTime();
        List<List<int[]>> schedule = Arrays.asList(
            Arrays.asList(new int[]{1,2}, new int[]{5,6}),
            Arrays.asList(new int[]{1,3}),
            Arrays.asList(new int[]{4,10})
        );
        for (int[] ft : sol.employeeFreeTime(schedule)) System.out.println(Arrays.toString(ft));
    }
}
