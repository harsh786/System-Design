import java.util.*;

public class Problem29_MaximumNumberOfVisiblePoints {
    public static int visiblePoints(List<List<Integer>> points, int angle, List<Integer> location) {
        List<Double> angles = new ArrayList<>();
        int same = 0;
        for (List<Integer> p : points) {
            int dx = p.get(0) - location.get(0), dy = p.get(1) - location.get(1);
            if (dx == 0 && dy == 0) { same++; continue; }
            angles.add(Math.toDegrees(Math.atan2(dy, dx)));
        }
        Collections.sort(angles);
        int n = angles.size();
        for (int i = 0; i < n; i++) angles.add(angles.get(i) + 360);
        int max = 0, l = 0;
        for (int r = 0; r < angles.size(); r++) {
            while (angles.get(r) - angles.get(l) > angle) l++;
            max = Math.max(max, r - l + 1);
        }
        return max + same;
    }
    public static void main(String[] args) {
        List<List<Integer>> pts = Arrays.asList(Arrays.asList(2,1),Arrays.asList(2,2),Arrays.asList(3,3));
        System.out.println(visiblePoints(pts, 90, Arrays.asList(1,1))); // 3
    }
}
