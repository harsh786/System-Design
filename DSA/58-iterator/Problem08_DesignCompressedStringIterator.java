import java.util.*;

public class Problem08_DesignCompressedStringIterator {
    // "L1e2t1C1o1d1e1" -> L,e,e,t,C,o,d,e
    char currentChar;
    int currentCount;
    String str;
    int idx;

    public Problem08_DesignCompressedStringIterator(String compressedString) {
        str = compressedString; idx = 0; advance();
    }

    void advance() {
        if (idx >= str.length()) return;
        currentChar = str.charAt(idx++);
        StringBuilder num = new StringBuilder();
        while (idx < str.length() && Character.isDigit(str.charAt(idx))) num.append(str.charAt(idx++));
        currentCount = Integer.parseInt(num.toString());
    }

    public char next() {
        if (!hasNext()) return ' ';
        char c = currentChar;
        currentCount--;
        if (currentCount == 0) advance();
        return c;
    }

    public boolean hasNext() { return currentCount > 0; }

    public static void main(String[] args) {
        Problem08_DesignCompressedStringIterator it = new Problem08_DesignCompressedStringIterator("L1e2t1C1o1d1e1");
        while (it.hasNext()) System.out.print(it.next());
        System.out.println();
    }
}
