import java.util.*;

public class Problem24_NumberOfStudentsUnableToEatLunch {
    public static int countStudents(int[] students, int[] sandwiches) {
        Queue<Integer> q = new LinkedList<>();
        for (int s : students) q.offer(s);
        int idx = 0, attempts = 0;
        while (!q.isEmpty() && attempts < q.size()) {
            if (q.peek() == sandwiches[idx]) { q.poll(); idx++; attempts = 0; }
            else { q.offer(q.poll()); attempts++; }
        }
        return q.size();
    }
    public static void main(String[] args) {
        System.out.println(countStudents(new int[]{1,1,0,0}, new int[]{0,1,0,1})); // 0
    }
}
