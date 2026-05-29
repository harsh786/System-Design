import java.util.*;

public class Problem27_BinaryWatch {
    public List<String> readBinaryWatch(int turnedOn) {
        List<String> result = new ArrayList<>();
        for (int h = 0; h < 12; h++) for (int m = 0; m < 60; m++)
            if (Integer.bitCount(h) + Integer.bitCount(m) == turnedOn)
                result.add(h + ":" + (m < 10 ? "0" : "") + m);
        return result;
    }
    public static void main(String[] args) { System.out.println(new Problem27_BinaryWatch().readBinaryWatch(1)); }
}
