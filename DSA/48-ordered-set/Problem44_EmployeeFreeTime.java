import java.util.*;

public class Problem44_EmployeeFreeTime {
    // LC 759: Find common free time intervals for all employees
    public static List<int[]> employeeFreeTime(List<List<int[]>> schedule) {
        TreeMap<Integer, Integer> map = new TreeMap<>();
        for (List<int[]> emp : schedule) {
            for (int[] iv : emp) {
                map.merge(iv[0], 1, Integer::sum);
                map.merge(iv[1], -1, Integer::sum);
            }
        }
        List<int[]> result = new ArrayList<>();
        int active = 0, prevEnd = -1;
        for (var e : map.entrySet()) {
            if (active == 0 && prevEnd >= 0 && e.getKey() > prevEnd)
                result.add(new int[]{prevEnd, e.getKey()});
            active += e.getValue();
            if (active == 0) prevEnd = e.getKey();
        }
        return result;
    }

    public static void main(String[] args) {
        List<List<int[]>> schedule = Arrays.asList(
            Arrays.asList(new int[]{1,2}, new int[]{5,6}),
            Arrays.asList(new int[]{1,3}),
            Arrays.asList(new int[]{4,10}));
        for (int[] iv : employeeFreeTime(schedule)) System.out.println(Arrays.toString(iv));
        // [3,4]
    }
}
