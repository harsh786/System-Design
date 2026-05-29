import java.util.*;

public class Problem16_CountingSortForGrades {
    public static int[] sortGrades(int[] grades) {
        int[] count = new int[101]; // 0-100
        for (int g : grades) count[g]++;
        int idx = 0;
        for (int i = 0; i <= 100; i++) while (count[i]-- > 0) grades[idx++] = i;
        return grades;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortGrades(new int[]{85, 92, 78, 95, 88, 72, 85})));
    }
}
