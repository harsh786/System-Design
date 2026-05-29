import java.util.*;

public class Problem17_CountingSortForASCIICharacters {
    public static String sortASCII(String s) {
        int[] count = new int[128];
        for (char c : s.toCharArray()) count[c]++;
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < 128; i++) while (count[i]-- > 0) sb.append((char)i);
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println(sortASCII("hello world!"));
    }
}
