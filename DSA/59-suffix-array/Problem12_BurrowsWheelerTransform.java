import java.util.*;

public class Problem12_BurrowsWheelerTransform {
    public static String bwt(String s) {
        s = s + "$";
        int n = s.length();
        Integer[] sa = new Integer[n];
        for (int i = 0; i < n; i++) sa[i] = i;
        String fs = s;
        Arrays.sort(sa, (a, b) -> {
            for (int k = 0; k < n; k++) {
                char ca = fs.charAt((a+k)%n), cb = fs.charAt((b+k)%n);
                if (ca != cb) return ca - cb;
            }
            return 0;
        });
        StringBuilder bwtStr = new StringBuilder();
        for (int i : sa) bwtStr.append(s.charAt((i + n - 1) % n));
        return bwtStr.toString();
    }

    public static void main(String[] args) {
        System.out.println(bwt("banana")); // annb$aa
        System.out.println(bwt("abracadabra")); // ard$rcaaaabb
    }
}
