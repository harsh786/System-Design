import java.util.*;

public class Problem50_AmbiguousCoordinates {
    public List<String> ambiguousCoordinates(String s) {
        s = s.substring(1, s.length()-1); // remove ()
        List<String> result = new ArrayList<>();
        for (int i = 1; i < s.length(); i++) {
            List<String> left = valid(s.substring(0,i)), right = valid(s.substring(i));
            for (String l : left) for (String r : right) result.add("("+l+", "+r+")");
        }
        return result;
    }
    private List<String> valid(String s) {
        List<String> res = new ArrayList<>();
        if (s.length() == 1 || s.charAt(0) != '0') res.add(s); // integer
        for (int i = 1; i < s.length(); i++) {
            String left = s.substring(0,i), right = s.substring(i);
            if (left.length() > 1 && left.charAt(0) == '0') continue;
            if (right.charAt(right.length()-1) == '0') continue;
            res.add(left+"."+right);
        }
        return res;
    }
    public static void main(String[] args) { System.out.println(new Problem50_AmbiguousCoordinates().ambiguousCoordinates("(123)")); }
}
