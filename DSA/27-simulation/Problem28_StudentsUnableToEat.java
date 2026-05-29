/**
 * Problem: Number of Students Unable to Eat Lunch (LeetCode 1700)
 * Approach: Count preferences; simulate until no match possible
 * Complexity: O(n) time, O(1) space
 * Production Analogy: Queue starvation detection in task scheduling
 */
public class Problem28_StudentsUnableToEat {
    public int countStudents(int[] students, int[] sandwiches) {
        int[] count = new int[2];
        for (int s : students) count[s]++;
        for (int s : sandwiches) {
            if (count[s] == 0) return count[0] + count[1];
            count[s]--;
        }
        return 0;
    }
    public static void main(String[] args) {
        System.out.println(new Problem28_StudentsUnableToEat()
            .countStudents(new int[]{1,1,0,0}, new int[]{0,1,0,1})); // 0
    }
}
