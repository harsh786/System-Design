import java.util.*;

public class Problem22_SequentialDigits {
    public List<Integer> sequentialDigits(int low, int high) {
        List<Integer> result = new ArrayList<>();
        for (int len = 2; len <= 9; len++)
            for (int start = 1; start <= 9-len+1; start++) {
                int num = 0;
                for (int i = start; i < start+len; i++) num = num*10+i;
                if (num >= low && num <= high) result.add(num);
            }
        Collections.sort(result);
        return result;
    }
    public static void main(String[] args) { System.out.println(new Problem22_SequentialDigits().sequentialDigits(100,300)); }
}
