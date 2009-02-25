from FeatureBuilder import FeatureBuilder
import Stemming.PorterStemmer as PorterStemmer
from EdgeFeatureBuilder import EdgeFeatureBuilder

class MultiEdgeFeatureBuilder(FeatureBuilder):
    def __init__(self, featureSet):
        FeatureBuilder.__init__(self, featureSet)
        self.edgeFeatureBuilder = EdgeFeatureBuilder(featureSet)
        self.ontologyFeatureBuilder = None
        self.noAnnType = False
        self.predictedRange = None
    
    def definePredictedValueRange(self, sentences, elementName):
        self.predictedRange = [None,None]
        for sentence in sentences:
            targetElements = sentence.findall(elementName)
            for element in targetElements:
                predictions = element.get("predictions")
                if predictions != None:
                    predictions = predictions.split(",")
                    for p in predictions:
                        splits = p.split(":")
                        value = float(splits[1])
                        if self.predictedRange[0] == None or self.predictedRange[0] > value:
                            self.predictedRange[0] = value
                        if self.predictedRange[1] == None or self.predictedRange[1] < value:
                            self.predictedRange[1] = value
    
    def buildStructureFeatures(self, sentenceGraph, paths):
        t1 = sentenceGraph.entityHeadTokenByEntity[self.entity1]
        t2 = sentenceGraph.entityHeadTokenByEntity[self.entity2]
        if paths.has_key(t1) and paths[t1].has_key(t2):
            path = paths[t1][t2]
            prevToken = None
            structure = ""
            for pathToken in path:
                if prevToken != None:
                    if sentenceGraph.dependencyGraph.has_edge(prevToken,pathToken):
                        structure += ">" + sentenceGraph.dependencyGraph.get_edge(prevToken,pathToken)[0].get("type") + ">"
                    elif sentenceGraph.dependencyGraph.has_edge(pathToken,prevToken):
                        structure += "<" + sentenceGraph.dependencyGraph.get_edge(pathToken,prevToken)[0].get("type") + "<"
                    else:
                        assert(False)
                structure += pathToken.get("POS")[0:1]
                prevToken = pathToken
            self.features[self.featureSet.getId(structure)] = 1
        
    def setFeatureVector(self, features=None, entity1=None, entity2=None):
        self.entity1 = entity1
        self.entity2 = entity2
        self.features = features
        self.edgeFeatureBuilder.setFeatureVector(features)
        if self.ontologyFeatureBuilder != None:
            self.ontologyFeatureBuilder.setFeatureVector(features)
    
    def buildPredictedValueFeatures(self, element, tag):
        predictions = element.get("predictions")
        if predictions != None:
            predictions = predictions.split(",")
            for p in predictions:
                splits = p.split(":")
                value = float(splits[1])
                value -= self.predictedRange[0]
                value /= (self.predictedRange[1] - self.predictedRange[0])
                assert(value >= 0 and value <= 1)
                #print tag + "_strength_"+splits[0], value
                self.features[self.featureSet.getId(tag + "_strength_"+splits[0])] = value
        else:
            #print tag + "_strength_"+str(element.get("type")), 1.0
            self.features[self.featureSet.getId(tag + "_strength_" + str(element.get("type")))] = 1.0
    
    def buildEntityFeatures(self, sentenceGraph):
        for token, entities in sentenceGraph.entitiesByToken.iteritems():
            if self.entity1 in entities:
                tokenFeatures = self.getTokenFeatures(token, sentenceGraph)
                for feature in tokenFeatures:
                    self.features[self.featureSet.getId("e1_"+feature)] = 1
            if self.entity2 in entities:
                tokenFeatures = self.getTokenFeatures(token, sentenceGraph)
                for feature in tokenFeatures:
                    self.features[self.featureSet.getId("e2_"+feature)] = 1
        if self.entity1 != None and self.entity2 != None:
            entityCombination = ""
            if self.entity1.get("isName") != None:
                if self.entity1.get("isName") == "True":
                    entityCombination += "e1_Entity_"
                else:
                    entityCombination += "e1_InteractionWord_"
                    if self.predictedRange != None:
                        self.buildPredictedValueFeatures(self.entity1, "e1")
            else:
                entityCombination += "e1_Entity_"
            if self.entity2.get("isName") != None:
                if self.entity2.get("isName") == "True":
                    entityCombination += "e2_Entity"
                else:
                    entityCombination += "e2_InteractionWord"
                    if self.predictedRange != None:
                        self.buildPredictedValueFeatures(self.entity2, "e2")
            else:
                entityCombination += "e2_Entity"
            self.features[self.featureSet.getId(entityCombination)] = 1
            self.features[self.featureSet.getId("eTypes_"+self.entity1.get("type")+"_"+self.entity2.get("type"))] = 1                
            
            if sentenceGraph.entityHeadTokenByEntity[self.entity1] == sentenceGraph.entityHeadTokenByEntity[self.entity2]:
                self.features[self.featureSet.getId("selfLoop")] = 1
                
    def getEdges(self, graph, path):
        """
        graph = Directed NetworkX graph
        path = list of token elements
        
        Builds a dictionary where edges are indexed by the indices of their
        start and end tokens in the path. F.e. to get the edges from path[1]
        to path[2] call return_value[1][2].
        """
        pathEdges = {}
        for i in range(0, len(path)):
            pathEdges[i] = {}
        for i in range(1, len(path)):
            pathEdges[i][i-1] = []
            pathEdges[i-1][i] = []
        edges = graph.edges()
        for i in range(1, len(path)):
            found = False
            for edge in edges:
                if edge[0] == path[i-1] and edge[1] == path[i]:
                    pathEdges[i-1][i].append(edge)
                    found = True
                elif edge[1] == path[i-1] and edge[0] == path[i]:
                    pathEdges[i][i-1].append(edge)
                    found = True
            assert(found==True)
        return pathEdges
    
    def getWalks(self, pathTokens, pathEdges, position=1, walk=None):
        """
        A path is defined by a list of tokens. But since there can be more than one edge
        between the same two tokens, there are multiple ways of getting from the first
        token to the last token. This function returns all of these "walks", i.e. the combinations
        of edges that can be travelled to get from the first to the last token of the path.
        """
        allWalks = []
        if walk == None:
            walk = []
        
        edges = pathEdges[position-1][position] + pathEdges[position][position-1]
        for edge in edges:
            if position < len(pathTokens)-1:
                allWalks.extend(self.getWalks(pathTokens, pathEdges, position+1, walk + [edge]))
            else:
                allWalks.append(walk + [edge])
        return allWalks
    
    def buildPathLengthFeatures(self, pathTokens):
        """
        Simple numeric features about the length of the path
        """
        self.features[self.featureSet.getId("len_tokens_"+str(len(pathTokens)))] = 1
        self.features[self.featureSet.getId("len")] = len(pathTokens)
    
    def buildSentenceFeatures(self, sentenceGraph):
        textCounts = {}
        for token in sentenceGraph.tokens:
            texts = self.getTokenAnnotatedType(token, sentenceGraph)
            #text = sentenceGraph.getTokenText(token)
            for text in texts:
                if not textCounts.has_key(text):
                    textCounts[text] = 0
                textCounts[text] += 1
        for k, v in textCounts.iteritems():
            self.features[self.featureSet.getId("count_"+k)] = v

    def buildTerminusTokenFeatures(self, pathTokens, sentenceGraph):
        """
        Token features for the first and last tokens of the path
        """
        for feature in self.getTokenFeatures(pathTokens[0], sentenceGraph):
            self.features[self.featureSet.getId("tokTerm1_"+feature)] = 1
        for feature in self.getTokenFeatures(pathTokens[-1], sentenceGraph):
            self.features[self.featureSet.getId("tokTerm2_"+feature)] = 1
        
        #self.features[self.featureSet.getId("tokTerm1POS_"+pathTokens[0].attrib["POS"])] = 1
        #self.features[self.featureSet.getId("tokTerm1txt_"+sentenceGraph.getTokenText(pathTokens[0]))] = 1
        #self.features[self.featureSet.getId("tokTerm2POS_"+pathTokens[-1].attrib["POS"])] = 1
        #self.features[self.featureSet.getId("tokTerm2txt_"+sentenceGraph.getTokenText(pathTokens[-1]))] = 1
    
    def buildWalkPaths(self, pathTokens, walks, sentenceGraph):
#        t1 = self.getTokenAnnotatedType(pathTokens[0], sentenceGraph)
#        t2 = self.getTokenAnnotatedType(pathTokens[-1], sentenceGraph)
        internalTypes = ""
        for token in pathTokens[0:-1]:
            annTypes = self.getTokenAnnotatedType(token, sentenceGraph)
            for annType in annTypes:
                internalTypes += "_" + annType
            internalTypes += "__"
        self.features[self.featureSet.getId("tokenPath"+internalTypes)] = 1
        
#        for walk in walks:
#            edgeString = ""
#            for edge in walk:
#                edgeString += "_" + edge[2].attrib["type"]
#            self.features[self.featureSet.getId("walkPath_"+t1+edgeString+"_"+t2)] = 1
    
    def buildPathGrams(self, length, pathTokens, pathEdges, sentenceGraph):
        """
        Goes through all the possible walks and builds features for subsections
        of "length" edges.
        """
        if pathEdges == None:
            return

        t1 = self.getTokenAnnotatedType(pathTokens[0], sentenceGraph)
        t2 = self.getTokenAnnotatedType(pathTokens[-1], sentenceGraph)

        walks = self.getWalks(pathTokens, pathEdges)
        self.buildWalkPaths(pathTokens, walks, sentenceGraph)
        dirGrams = []
        for walk in walks:
            dirGrams.append("")
        for i in range(len(pathTokens)-1): # len(pathTokens) == len(walk)
            for j in range(len(walks)):
                if walks[j][i][0] == pathTokens[i]:
                    dirGrams[j] += "F"
                else:
                    dirGrams[j] += "R"
                if i >= length-1:
                    styleGram = dirGrams[j][i-(length-1):i+1]
                    edgeGram = "depGram_" + styleGram
                    # Label tokens by their role in the xgram
                    for token in pathTokens[i-(length-1)+1:i+1]:
                        for feature in self.getTokenFeatures(token, sentenceGraph, annotatedType=(self.maximum == True)):
                            self.features[self.featureSet.getId("tok_"+styleGram+feature)] = 1
                    # Label edges by their role in the xgram
                    position = 0
                    tokenTypeGram = ""
                    for edge in walks[j][i-(length-1):i+1]:
                        self.features[self.featureSet.getId("dep_"+styleGram+str(position)+"_"+edge[2].get("type"))] = 1
                        position += 1
                        edgeGram += "_" + edge[2].get("type")
                    self.features[self.featureSet.getId(edgeGram)] = 1
                    for type1 in t1:
                        for type2 in t2:
                            self.features[self.featureSet.getId(type1+"_"+edgeGram+"_"+type2)] = 1
        for dirGram in dirGrams:
            self.features[self.featureSet.getId("edge_directions_"+dirGram)] = 1
    
    def addType(self, token, sentenceGraph, prefix="annType_"):
        types = self.getTokenAnnotatedType(token, sentenceGraph)
        for type in types:
            self.features[self.featureSet.getId(prefix+type)] = 1
    
    def buildPathEdgeFeatures(self, pathTokens, pathEdges, sentenceGraph):
        if pathEdges == None:
            return
        
        edgeList = []
        for i in range(1, len(pathTokens)):
            edgeList.extend(pathEdges[i][i-1])
            edgeList.extend(pathEdges[i-1][i])
        for edge in edgeList:
            depType = edge[2].get("type")
            self.features[self.featureSet.getId("dep_"+depType)] = 1
            # Token 1
            self.features[self.featureSet.getId("txt_"+sentenceGraph.getTokenText(edge[0]))] = 1
            self.features[self.featureSet.getId("POS_"+edge[0].get("POS"))] = 1
            self.addType(edge[0], sentenceGraph, prefix="annType_")
            # Token 2
            self.features[self.featureSet.getId("txt_"+sentenceGraph.getTokenText(edge[1]))] = 1
            self.features[self.featureSet.getId("POS_"+edge[1].get("POS"))] = 1
            self.addType(edge[1], sentenceGraph, prefix="annType_")
            
            # g-d features
            gText = sentenceGraph.getTokenText(edge[0])
            dText = sentenceGraph.getTokenText(edge[1])
            gPOS = edge[0].get("POS")
            dPOS = edge[1].get("POS")
            gAT = "noAnnType"
            dAT = "noAnnType"
            if sentenceGraph.tokenIsEntityHead[edge[0]] != None:
                gATs = self.getTokenAnnotatedType(edge[0], sentenceGraph)
            if sentenceGraph.tokenIsEntityHead[edge[1]] != None:
                dATs = self.getTokenAnnotatedType(edge[1], sentenceGraph)
            self.features[self.featureSet.getId("gov_"+gText+"_"+dText)] = 1
            self.features[self.featureSet.getId("gov_"+gPOS+"_"+dPOS)] = 1
            for gAT in gATs:
                for dAT in dATs:
                    self.features[self.featureSet.getId("gov_"+gAT+"_"+dAT)] = 1
            
            for gAT in gATs:
                self.features[self.featureSet.getId("triple_"+gAT+"_"+depType+"_"+dAT)] = 1
            #self.features[self.featureSet.getId("triple_"+gPOS+"_"+depType+"_"+dPOS)] = 1
            #self.features[self.featureSet.getId("triple_"+gText+"_"+depType+"_"+dText)] = 1

#            # Features for edge-type/token combinations that define the governor/dependent roles
#            self.features[self.featureSet.getId("depgov_"+depType+"_"+dText)] = 1
#            self.features[self.featureSet.getId("depgov_"+depType+"_"+dPOS)] = 1
#            self.features[self.featureSet.getId("depgov_"+depType+"_"+dAT)] = 1
#            self.features[self.featureSet.getId("depdep_"+gText+"_"+depType)] = 1
#            self.features[self.featureSet.getId("depdep_"+gPOS+"_"+depType)] = 1
#            self.features[self.featureSet.getId("depdep_"+gAT+"_"+depType)] = 1

    def buildSingleElementFeatures(self, pathTokens, pathEdges, sentenceGraph):
        # Edges directed relative to the path
        for i in range(1,len(pathTokens)):
            if pathEdges != None:
                for edge in pathEdges[i][i-1]:
                    depType = edge[2].get("type")
                    self.features[self.featureSet.getId("dep_"+depType+"Forward_")] = 1
                for edge in pathEdges[i-1][i]:
                    depType = edge[2].get("type")
                    self.features[self.featureSet.getId("dep_Reverse_"+depType)] = 1

        # Internal tokens
        for i in range(1,len(pathTokens)-1):
            self.features[self.featureSet.getId("internalPOS_"+pathTokens[i].get("POS"))]=1
            self.features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(pathTokens[i]))]=1
        # Internal dependencies
        for i in range(2,len(pathTokens)-1):
            if pathEdges != None:
                for edge in pathEdges[i][i-1]:
                    self.features[self.featureSet.getId("internalDep_"+edge[2].get("type"))] = 1
                for edge in pathEdges[i-1][i]:
                    self.features[self.featureSet.getId("internalDep_"+edge[2].get("type"))] = 1

    def buildEdgeCombinations(self, pathTokens, pathEdges, sentenceGraph):
            
#        if edges[0][1]:
#            features[self.featureSet.getId("internalPOS_"+edges[0][0][0].attrib["POS"])]=1
#            features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(edges[0][0][0]))]=1
#        else:
#            features[self.featureSet.getId("internalPOS_"+edges[0][0][1].attrib["POS"])]=1
#            features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(edges[0][0][1]))]=1
#        if edges[-1][1]:
#            features[self.featureSet.getId("internalPOS_"+edges[-1][0][1].attrib["POS"])]=1
#            features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(edges[-1][0][1]))]=1
#        else:
#            features[self.featureSet.getId("internalPOS_"+edges[-1][0][0].attrib["POS"])]=1
#            features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(edges[-1][0][0]))]=1
#        for i in range(1,len(edges)-1):
#            features[self.featureSet.getId("internalPOS_"+edges[i][0][0].attrib["POS"])]=1
#            features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(edges[i][0][0]))]=1
#            features[self.featureSet.getId("internalPOS_"+edges[i][0][1].attrib["POS"])]=1
#            features[self.featureSet.getId("internalTxt_"+sentenceGraph.getTokenText(edges[i][0][1]))]=1
#            features[self.featureSet.getId("internalDep_"+edges[i][0][2].attrib["type"])]=1
        
        return
        # Edge bigrams
        for i in range(1,len(pathTokens)-1):
            edgesForward1 = pathEdges[i][i-1]
            edgesReverse1 = pathEdges[i-1][i]
            edgesForward2 = pathEdges[i][i+1]
            edgesReverse2 = pathEdges[i+1][i]
            for e1 in edgesForward1:
                for e2 in edgesForward2:
                    features[self.featureSet.getId("dep_"+e1[2].get("type")+">"+e2[2].get("type")+">")] = 1
            for e1 in edgesReverse1:
                for e2 in edgesReverse2:
                    features[self.featureSet.getId("dep_"+e1[2].get("type")+"<"+e2[2].get("type")+"<")] = 1
            for e1 in edgesForward1:
                for e2 in edgesReverse2:
                    features[self.featureSet.getId("dep_"+e1[2].get("type")+">"+e2[2].get("type")+"<")] = 1
            for e1 in edgesReverse1:
                for e2 in edgesForward2:
                    features[self.featureSet.getId("dep_"+e1[2].get("type")+"<"+e2[2].get("type")+">")] = 1
                
#        for i in range(1,len(edges)):
#            type1 = edges[i-1][0][2].attrib["type"]
#            type2 = edges[i][0][2].attrib["type"]
#            if edges[i-1][1] and edges[i][1]:
#                features[self.featureSet.getId("dep_"+type1+">"+type2+">")] = 1
#            elif edges[i-1][1] and edges[i][0]:
#                features[self.featureSet.getId("dep_"+type1+">"+type2+"<")] = 1
#            elif edges[i-1][0] and edges[i][0]:
#                features[self.featureSet.getId("dep_"+type1+"<"+type2+"<")] = 1
#            elif edges[i-1][0] and edges[i][1]:
#                features[self.featureSet.getId("dep_"+type1+"<"+type2+">")] = 1

    def buildTerminusFeatures(self, token, ignoreEdges, prefix, sentenceGraph): 
        # Attached edges
        inEdges = sentenceGraph.dependencyGraph.in_edges(token)
        for edge in inEdges:
            if edge in ignoreEdges:
                continue
            self.features[self.featureSet.getId(prefix+"HangingIn_"+edge[2].get("type"))] = 1
            for feature in self.getTokenFeatures(edge[0], sentenceGraph):
                self.features[self.featureSet.getId(prefix+"HangingIn_"+feature)] = 1
        outEdges = sentenceGraph.dependencyGraph.out_edges(token)
        for edge in outEdges:
            if edge in ignoreEdges:
                continue
            self.features[self.featureSet.getId(prefix+"HangingOut_"+edge[2].get("type"))] = 1
            for feature in self.getTokenFeatures(edge[1], sentenceGraph):
                self.features[self.featureSet.getId(prefix+"HangingOut_"+feature)] = 1