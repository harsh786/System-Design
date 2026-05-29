public class Problem18_BrowserHistoryWithDLL {
    static class Node{String url;Node prev,next;Node(String u){url=u;}}
    Node cur;
    Problem18_BrowserHistoryWithDLL(String homepage){cur=new Node(homepage);}
    void visit(String url){Node n=new Node(url);cur.next=n;n.prev=cur;cur=n;}
    String back(int steps){while(steps-->0&&cur.prev!=null)cur=cur.prev;return cur.url;}
    String forward(int steps){while(steps-->0&&cur.next!=null)cur=cur.next;return cur.url;}
    
    public static void main(String[] args) {
        Problem18_BrowserHistoryWithDLL b=new Problem18_BrowserHistoryWithDLL("google.com");
        b.visit("fb.com");b.visit("yt.com");
        System.out.println(b.back(1)); // fb.com
        System.out.println(b.forward(1)); // yt.com
    }
}
