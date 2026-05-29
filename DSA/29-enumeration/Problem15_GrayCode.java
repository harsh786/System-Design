import java.util.*;

public class Problem15_GrayCode {
    public List<Integer> grayCode(int n) {
        List<Integer> result = new ArrayList<>();
        for (int i = 0; i < (1 << n); i++) result.add(i ^ (i >> 1));
        return result;
    }

    public static void main(String[] args) { System.out.println(new Problem15_GrayCode().grayCode(3)); }
}
