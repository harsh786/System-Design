import java.util.*;

public class Problem15_CountingSortForAges {
    public static int[] sortAges(int[] ages) {
        int[] count = new int[151]; // ages 0-150
        for (int a : ages) count[a]++;
        int idx = 0;
        for (int i = 0; i < 151; i++) while (count[i]-- > 0) ages[idx++] = i;
        return ages;
    }

    public static void main(String[] args) {
        int[] ages = {25, 18, 30, 25, 18, 65, 30};
        System.out.println(Arrays.toString(sortAges(ages)));
    }
}
