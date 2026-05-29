import java.util.*;

public class Problem43_DLLSkipPointers {
    // DLL with skip pointers for O(sqrt(n)) access
    static class Node{int val,index;Node prev,next,skip;Node(int v,int i){val=v;index=i;}}
    
    Node head;int size;int skipSize;
    List<Node> skipList=new ArrayList<>();
    
    void build(int[] arr){
        skipSize=(int)Math.sqrt(arr.length);
        Node prev2=null;
        for(int i=0;i<arr.length;i++){
            Node n=new Node(arr[i],i);
            if(prev2!=null){prev2.next=n;n.prev=prev2;}else head=n;
            if(i%skipSize==0)skipList.add(n);
            prev2=n;
        }
        size=arr.length;
    }
    
    int get(int index){
        int block=index/skipSize;
        Node cur=skipList.get(Math.min(block,skipList.size()-1));
        while(cur.index<index)cur=cur.next;
        while(cur.index>index)cur=cur.prev;
        return cur.val;
    }
    
    public static void main(String[] args) {
        Problem43_DLLSkipPointers sp=new Problem43_DLLSkipPointers();
        sp.build(new int[]{10,20,30,40,50,60,70,80,90});
        System.out.println("Index 5: "+sp.get(5)); // 60
        System.out.println("Index 0: "+sp.get(0)); // 10
    }
}
